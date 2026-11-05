"""Parse SaferProducts.gov incident CSV exports (bulk SPDB.zip and Public Search export share one format)."""

import csv
import hashlib
import io
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, datetime

DISCLAIMER_PREFIX = "Disclaimer:"


def _text(value: str) -> str | None:
    return value if value.strip() else None


def _required_text(value: str) -> str:
    return value


def _date(value: str) -> date | None:
    value = value.strip()
    return datetime.strptime(value, "%m/%d/%Y").date() if value else None


def _required_date(value: str) -> date:
    parsed = _date(value)
    if parsed is None:
        raise ValueError("missing required date")
    return parsed


def _yes_no(value: str) -> bool | None:
    return {"yes": True, "no": False}.get(value.strip().lower())


def _flag(value: str) -> bool:
    return value.strip().lower() == "yes"


def _severity(value: str) -> str:
    """Public Search exports write 'Injury - Seen by...'; the bulk file writes 'Injury, Seen by...'."""
    head, sep, tail = value.strip().partition(" - ")
    return f"{head}, {tail}" if sep else value.strip()


def _upc(value: str) -> str | None:
    """The bulk file prefixes UPCs with an apostrophe so spreadsheets keep leading zeros."""
    return _text(value.strip().removeprefix("'"))


def _int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value.isdigit() else None


def _report_list(value: str) -> list[str]:
    return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]


def _product_type(value: str) -> str | None:
    """Drop the trailing ' (NNNN)' product code; the code has its own column."""
    value = value.strip()
    if value.endswith(")") and "(" in value:
        head, _, tail = value.rpartition("(")
        if tail[:-1].isdigit():
            value = head.strip()
    return value or None


# CSV header -> (column in source.incident, converter). Order matches the export.
COLUMNS: dict[str, tuple[str, Callable[[str], object]]] = {
    "Report No.": ("report_no", _required_text),
    "Report Date": ("report_date", _required_date),
    "Sent to Manufacturer / Importer / Private Labeler": ("sent_to_manufacturer_date", _date),
    "Publication Date": ("publication_date", _required_date),
    "Category of Submitter": ("submitter_category", _required_text),
    "Product Description": ("product_description", _required_text),
    "Product Category": ("product_category", _required_text),
    "Product Sub Category": ("product_subcategory", _required_text),
    "Product Type": ("product_type", _product_type),
    "Product Code": ("product_code", _required_text),
    "Manufacturer / Importer / Private Labeler Name": ("manufacturer_name", _required_text),
    "Brand": ("brand", _text),
    "Model Name or Number": ("model", _text),
    "Serial Number": ("serial_number", _text),
    "UPC": ("upc", _upc),
    "Date Manufactured": ("date_manufactured", _date),
    "Manufacturer Date Code": ("manufacturer_date_code", _text),
    "Retailer": ("retailer", _text),
    "Retailer State": ("retailer_state", _text),
    "Purchase Date": ("purchase_date", _date),
    "Purchase Date Is Estimate": ("purchase_date_is_estimate", _flag),
    "Incident Description": ("incident_description", _required_text),
    "City": ("city", _text),
    "State": ("state", _text),
    "ZIP": ("zip", _text),
    "Location": ("location", _text),
    "(Primary) Victim Severity": ("severity", _severity),
    "(Primary) Victim's Sex": ("victim_sex", _text),
    "My Relation To The (Primary) Victim": ("relation_to_victim", _text),
    "(Primary) Victim's Age (years)": ("victim_age", _int),
    "Submitter Has Product": ("submitter_has_product", _yes_no),
    "Product Was Damaged Before Incident": ("damaged_before_incident", _yes_no),
    "Damage Description": ("damage_description", _text),
    "Damage Repaired": ("damage_repaired", _yes_no),
    "Product Was Modified Before Incident": ("modified_before_incident", _yes_no),
    "Have You Contacted The Manufacturer": ("contacted_manufacturer", _yes_no),
    "If Not Do You Plan To": ("plans_to_contact", _yes_no),
    "Answer Explanation": ("answer_explanation", _text),
    "Company Comments": ("company_comments", _text),
    "Associated Report Numbers": ("associated_report_nos", _report_list),
}

INCIDENT_COLUMNS = [column for column, _ in COLUMNS.values()]


@dataclass(frozen=True)
class SourceRow:
    report_no: str
    raw: dict[str, str]
    row_sha256: str
    typed: dict[str, object]


def parse_export(data: bytes) -> Iterator[SourceRow]:
    """Yield incident rows. Recall rows that Public Search mixes into keyword exports are skipped."""
    csv.field_size_limit(1 << 30)
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252")
    if text.startswith(DISCLAIMER_PREFIX) or text.startswith('"' + DISCLAIMER_PREFIX):
        text = text.split("\n", 1)[1]
    reader = csv.DictReader(io.StringIO(text, newline=""))
    missing = set(COLUMNS) - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"export is missing columns: {sorted(missing)}")
    for raw in reader:
        if not raw["Report No."][:8].isdigit():
            continue
        raw = {header: raw[header] or "" for header in COLUMNS}
        typed = {column: convert(raw[header]) for header, (column, convert) in COLUMNS.items()}
        digest = hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        yield SourceRow(report_no=raw["Report No."], raw=raw, row_sha256=digest, typed=typed)
