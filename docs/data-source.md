# SaferProducts.gov data source

What the ingestion code relies on, as observed on 2026-11-05.

## Bulk snapshot

`https://www.SaferProducts.gov/SPDB.zip` (about 40 MB) holds `IncidentReports.csv`, `Recalls.csv`, and `Disclaimer.txt`. The 2026-11-05 copy has 70,000 incident reports, report dates 2011 to 2026-10-19, publication dates up to 2026-11-04.

- The first line is the CPSC disclaimer. The header is the second line.
- The file is Windows-1252, not UTF-8. A UTF-8 decode turns curly quotes into replacement characters, which would alter consumer narratives.
- UPCs carry a leading apostrophe (a spreadsheet text guard).
- Company Comments start with the response date and company name: `(10/21/2026) LG Electronics, USA: ...`. One field can hold several responses.
- Narratives keep their original line breaks.
- There is no incident date. `Report Date` is when the report was submitted, `Publication Date` is when it went public.
- `Product Type` sometimes loses its trailing ` (code)`. `Product Code` is always present.

## Incremental sync

There is no public incident API (`/RestWebServices` serves recalls only, `/WebApi/...` needs credentials). The supported public path is the Public Search site:

1. `GET /PublicSearch` for the session cookie and `__RequestVerificationToken`.
2. `POST /PublicSearch` with `searchParameter.IncidentType=Report`, `searchParameter.DateRange=Custom Dates`, `searchParameter.StartDate` and `EndDate` as `MM/DD/YYYY`. The range filters on publication date.
3. `GET /PublicSearch/Result?target=csv&handler=export` returns the session's results as CSV, in the same 40 columns as the bulk file.

The export renders the same records less faithfully than the bulk file. It writes severities as `Injury - X` instead of `Injury, X`, strips line breaks and comment dates, drops Associated Report Numbers, and adds trailing spaces to dates. So an incremental row only inserts a new report or refreshes a report that an earlier incremental row supplied. It never overwrites a record held from a bulk snapshot. Every received row is still kept verbatim in `source.incident_version`.

## Source links

A Public Search detail page is addressed by an internal id (`/PublicSearch/Result?id=1542836&handler=Detail`) that neither export contains. The prototype cites the Report No., the batch, and the file hash instead, and links to Public Search.
