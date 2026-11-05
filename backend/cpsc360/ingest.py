"""Load SaferProducts.gov incident reports.

  python -m cpsc360.ingest init-db
  python -m cpsc360.ingest bulk [--file SPDB.zip]            full public database (https://www.SaferProducts.gov/SPDB.zip)
  python -m cpsc360.ingest sync [--since YYYY-MM-DD]         incremental, via Public Search export filtered by publication date
  python -m cpsc360.ingest derive                            rebuild the inference schema from source

Every command is idempotent. Re-running bulk or sync over the same data changes nothing.
"""

import argparse
import collections
import hashlib
import io
import re
import sys
import zipfile
from datetime import date, timedelta
from importlib import resources

import httpx
from psycopg.types.json import Jsonb

from . import derive
from .db import connect
from .source_csv import INCIDENT_COLUMNS, SourceRow, parse_export

BULK_URL = "https://www.SaferProducts.gov/SPDB.zip"
SEARCH_URL = "https://www.saferproducts.gov/PublicSearch"
EXPORT_URL = "https://www.saferproducts.gov/PublicSearch/Result?target=csv&handler=export"
SYNC_OVERLAP_DAYS = 14
SYNC_WINDOW_DAYS = 31

_UPSERT_INCIDENT = (
    f"INSERT INTO source.incident (current_sha256, batch_id, {', '.join(INCIDENT_COLUMNS)}) "
    f"VALUES (%(current_sha256)s, %(batch_id)s, {', '.join(f'%({c})s' for c in INCIDENT_COLUMNS)}) "
    "ON CONFLICT (report_no) DO UPDATE SET "
    + ", ".join(f"{c} = EXCLUDED.{c}" for c in ["current_sha256", "batch_id", *INCIDENT_COLUMNS[1:]])
)


def init_db() -> None:
    schema = resources.files("cpsc360").joinpath("schema.sql").read_text()
    with connect() as conn:
        conn.execute(schema)
    print("schema applied")


def load(rows: list[SourceRow], kind: str, source_url: str, params: dict, file_sha256: str) -> dict:
    with connect() as conn, conn.cursor() as cur:
        batch_id = cur.execute(
            "INSERT INTO source.ingest_batch (kind, source_url, params, file_sha256) VALUES (%s, %s, %s, %s) RETURNING id",
            (kind, source_url, Jsonb(params), file_sha256),
        ).fetchone()[0]
        current = {
            report_no: (sha, held_kind)
            for report_no, sha, held_kind in cur.execute(
                "SELECT i.report_no, i.current_sha256, b.kind FROM source.incident i "
                "JOIN source.ingest_batch b ON b.id = i.batch_id"
            ).fetchall()
        }
        by_report = {row.report_no: row for row in rows}
        changed = [row for row in by_report.values() if current.get(row.report_no, (None,))[0] != row.row_sha256]
        # The Public Search export is a lossier rendering than the bulk file (no newlines, no comment dates,
        # no associated reports), so it only adds reports or refreshes ones it supplied itself.
        applied = [
            row for row in changed
            if kind == "bulk" or current.get(row.report_no, (None, "incremental"))[1] == "incremental"
        ]
        cur.executemany(
            "INSERT INTO source.incident_version (report_no, row_sha256, raw, batch_id) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT DO NOTHING",
            [(row.report_no, row.row_sha256, Jsonb(row.raw), batch_id) for row in changed],
        )
        cur.executemany(
            _UPSERT_INCIDENT,
            [{**row.typed, "current_sha256": row.row_sha256, "batch_id": batch_id} for row in applied],
        )
        stats = {
            "row_count": len(by_report),
            "inserted": sum(1 for row in applied if row.report_no not in current),
            "updated": sum(1 for row in applied if row.report_no in current),
            "unchanged": len(by_report) - len(changed),
            "kept_bulk": len(changed) - len(applied),
        }
        cur.execute(
            "UPDATE source.ingest_batch SET finished_at = clock_timestamp(), row_count = %(row_count)s, inserted = %(inserted)s, "
            "updated = %(updated)s, unchanged = %(unchanged)s, kept_bulk = %(kept_bulk)s WHERE id = %(id)s",
            {**stats, "id": batch_id},
        )
    print(f"batch {batch_id} ({kind}): {stats}")
    return {"batch_id": batch_id, **stats}


def bulk(path: str | None) -> dict:
    if path:
        data = open(path, "rb").read()
    else:
        data = httpx.get(BULK_URL, follow_redirects=True, timeout=600).raise_for_status().content
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        rows = list(parse_export(archive.read("IncidentReports.csv")))
    return load(rows, "bulk", path or BULK_URL, {}, hashlib.sha256(data).hexdigest())


def _export_window(client: httpx.Client, start: date, end: date) -> bytes:
    """Public Search keeps the query in the session; the CSV export then returns that result set."""
    page = client.get(SEARCH_URL).raise_for_status().text
    token = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', page)
    if not token:
        raise RuntimeError("Public Search page has no anti-forgery token; the site layout changed")
    client.post(
        SEARCH_URL,
        data={
            "__RequestVerificationToken": token.group(1),
            "searchParameter.IncidentType": "Report",
            "searchParameter.DateRange": "Custom Dates",
            "searchParameter.StartDate": start.strftime("%m/%d/%Y"),
            "searchParameter.EndDate": end.strftime("%m/%d/%Y"),
            "searchParameter.Keyword": "",
        },
    ).raise_for_status()
    return client.get(EXPORT_URL).raise_for_status().content


def sync(since: date | None) -> list[dict]:
    if since is None:
        with connect() as conn:
            latest = conn.execute("SELECT max(publication_date) FROM source.incident").fetchone()[0]
        if latest is None:
            raise SystemExit("database is empty; run `bulk` first")
        since = latest - timedelta(days=SYNC_OVERLAP_DAYS)
    results = []
    start = since
    while start <= date.today():
        end = min(start + timedelta(days=SYNC_WINDOW_DAYS - 1), date.today())
        with httpx.Client(follow_redirects=True, timeout=300, headers={"User-Agent": "cpsc360-prototype"}) as client:
            data = _export_window(client, start, end)
        rows = list(parse_export(data))
        params = {"publication_date_from": start.isoformat(), "publication_date_to": end.isoformat()}
        results.append(load(rows, "incremental", EXPORT_URL, params, hashlib.sha256(data).hexdigest()))
        start = end + timedelta(days=1)
    return results


def rebuild_inference() -> dict:
    with connect() as conn, conn.cursor() as cur:
        records = cur.execute(
            "SELECT report_no, manufacturer_name, brand, model, incident_description FROM source.incident"
        ).fetchall()
        norm, hazards = [], []
        spellings: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        for report_no, manufacturer, brand, model, narrative in records:
            key = derive.manufacturer_key(manufacturer)
            spellings[key][manufacturer.strip()] += 1
            norm.append((
                report_no, key, derive.brand_key(brand), derive.product_model_key(model, brand, manufacturer),
                derive.match_text(brand) or None, derive.match_text(model) or None, derive.NORM_METHOD,
            ))
            for hazard, evidence in derive.tag_hazards(narrative).items():
                hazards.append((report_no, hazard, evidence, derive.HAZARD_METHOD))
        cur.execute("TRUNCATE inference.incident_norm, inference.incident_hazard, inference.manufacturer")
        cur.executemany(
            "INSERT INTO inference.incident_norm (report_no, manufacturer_key, brand_key, model_key, brand_text, model_text, method) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            norm,
        )
        cur.executemany("INSERT INTO inference.incident_hazard VALUES (%s, %s, %s, %s)", hazards)
        cur.executemany(
            "INSERT INTO inference.manufacturer VALUES (%s, %s, %s, %s, %s)",
            [
                (key, counts.most_common(1)[0][0], len(counts), sum(counts.values()), derive.NORM_METHOD)
                for key, counts in spellings.items()
            ],
        )
    stats = {"incidents": len(records), "hazard_tags": len(hazards), "manufacturers": len(spellings)}
    print(f"inference rebuilt: {stats}")
    return stats


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="cpsc360.ingest")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db")
    bulk_parser = commands.add_parser("bulk")
    bulk_parser.add_argument("--file")
    sync_parser = commands.add_parser("sync")
    sync_parser.add_argument("--since", type=date.fromisoformat)
    commands.add_parser("derive")
    args = parser.parse_args(argv)
    if args.command == "init-db":
        init_db()
    elif args.command == "bulk":
        bulk(args.file)
        rebuild_inference()
    elif args.command == "sync":
        try:
            sync(args.since)
        finally:
            rebuild_inference()
    else:
        rebuild_inference()


if __name__ == "__main__":
    main(sys.argv[1:])
