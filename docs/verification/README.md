# Verification at e1449ac

A delegate (`codex/gpt-6.1-sol`) ran the real app against the full 70,004-report database after the third review fix round. Verdict: pass on all 15 checks.

| Check | Result |
| --- | --- |
| Seven-step demo | Millie Moon search, skin-irritation evidence, related reasons, compare, investigation, a summary whose 15 claims all cite reports, and the Diapers spike (339 shown, 339 opened). `1-7-diapers-spike.png`, `1-7-diapers-explorer.png` |
| Search snippets | `fire crews`: 95 results, verbatim excerpts with no inserted commas. `2-fire-crews.png` |
| Model filter `GT` | 13 results |
| Hazard drill-down inside a filter | Fire plus Burn / scald shows 5,769 and opens 5,769. `4-fire-burn.png` |
| Missing values | "Not reported" shows 1 and does not navigate. `5-not-reported.png` |
| Evidence marking | `fire` marked, `fireplace` not |
| Tests and build | Backend 26 passed, frontend 15 passed, production build succeeded |
| Symbol-only filters | Model `?` returns 19, brand `?` returns 4, all with that literal value |
| Cross-maker models | A tree stand (model X1) and a Samsung report (model "Samsung") show no "Same model" reason |
| Accents | `GE Café` highlighted. `BabyBjorn` and `BABYBJÖRN` return the same 8 reports. "Pelotón Tread +" links to "Peloton Tread +" as the same model |
| Reported spellings | A summary over two `MIDEA USA, INC.` reports quotes that spelling |
| Hyphenated codes | `AW-R-NA-BLUE` keys as `awrnablue` |
