# Combined early-warning watchlist

**341 of 350 flags had no qualifying notice in the next year.** Nine flagged reports named a model in a later action. Eight also described the stated hazard. The combo caught 7 of 54 reachable notices (13%). Three of its nine model hits pointed to the same Bugaboo Giraffe recall.

## Results

Paired numbers show strict / loose. Random means expected positive reports if we drew the same number uniformly from all 7,468 publications. Lead is in days.

| Watchlist | Flags | Hits | Precision | Random hits | Lift | Distinct notices | Median lead | Already recalled or warned |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Combined OR | 350 | 9 / 8 | 2.57% / 2.29% | 4.87 / 6.23 | 1.85 / 1.28 | 7 / 6 | 55 / 53 | 29 |
| Prior admission | 7 | 0 / 0 | 0.00% / 0.00% | 0.10 / 0.12 | 0.00 / 0.00 | 0 / 0 | n/a / n/a | 0 |
| Known mechanism | 14 | 1 / 1 | 7.14% / 7.14% | 0.19 / 0.25 | 5.13 / 4.01 | 1 / 1 | 101 / 101 | 2 |
| Specific report | 335 | 8 / 7 | 2.39% / 2.09% | 4.67 / 5.97 | 1.71 / 1.17 | 6 / 5 | 45.5 / 36 | 27 |
| After recall repair | 1 | 0 / 0 | 0.00% / 0.00% | 0.01 / 0.02 | 0.00 / 0.00 | 0 / 0 | n/a / n/a | 1 |
| All reports | 7,468 | 104 / 133 | 1.39% / 1.78% | 104.00 / 133.00 | 1.00 / 1.00 | 54 / 73 | 135 / 136 | 457 |

A uniform random draw of 350 reports gives a central 95% range of 1–9 strict hits and 2–11 loose hits (hypergeometric distribution). Both observed totals fall inside those ranges. The mechanism rule's one hit was a BowFlex 1090 plate striking the user, 101 days before the notice. The report named the model and gave a compatible purchase date but no serial. [BowFlex recall](https://www.cpsc.gov/Recalls/2025/Johnson-Health-Tech-Trading-Recalls-BowFlex-Adjustable-Dumbbells-Due-to-Impact-Hazard-Including-3-7-Million-Sold-by-Nautilus-Inc)

## Rules and scoring

Commit `29661ae` froze the [rules](../backend/scripts/watchlist_rules.py), [mechanisms](../backend/scripts/watchlist_mechanisms.py), protocol and notice archive before this evaluation. Earlier investigations had examined some of these years. This retrospective replay uses the current version of each narrative. We made no post-score detector changes.

1. **Prior admission.** Match normalized, nonempty maker and model to a hospital admission published 1–90 days earlier. Reports on the same publication day enter history together.
2. **Known mechanism.** Require product context and narrative evidence of dumbbell plate release, pressure-cooker lid or contents ejection, or expanding-bead ingestion with bowel obstruction. The fixed expressions cite recalls 12-194, 21-035, 23-256 and 13-071. We omitted accidental range-knob contact because we could not verify that precise mechanism in a pre-2024 ledger notice.
3. **Specific report.** Require a model, a serial or lot identifier, a listed physical failure, and structured injury/death or explicit near-injury wording. A single report can fire on arrival. Two of its eight strict hits repeated all or part of the model code in the serial field.
4. **After recall repair.** Require completed recall-remedy language, recurrence language and a physical failure in the same narrative. Co-occurrence can miss genuine repair stories. A documented prior action makes a report ineligible for early credit.

The holdout covers publications from January 1, 2024 through November 4, 2025, plus 860 earlier reports for rule history only. The public snapshot ends November 4, 2026. All flags stay in the denominator. A future action must occur 1–365 days after publication. A known earlier or same-day product action blocks credit. Strict accepts a listed model number or distinctive listed model name, with no known scope conflict. A missing serial leaves individual unit eligibility uncertain. Loose requires matching maker, product type and hazard. A known model, retailer or serial conflict excludes the pair. A different hazard can still earn strict model credit. Each report counts once per tier. Lead uses its earliest matching action. Reachable notices have a strict, eligible link to at least one holdout report.

## Verification and limitations

Reviewers used the same product-scope criteria across flagged and unflagged reports. We read 1,974 broad candidate pairs, checked 30 more from the revised outcome matcher, and searched separately for model prefixes and product names. Every credited link has a [pair-level decision](../backend/tests/fixtures/watchlist-adjudications.csv). The independent search added five unflagged links. A missing brand, model, alias or scope detail can still hide a match. The measured lead is to a public notice. The data do not show when CPSC first learned of the issue.

Every strict hit and a [fixed random sample of 20 negatives](../backend/tests/fixtures/watchlist-negative-audit.csv) received individual review. We ranked negative report IDs by SHA-256 of `20:<report_no>` and took the first 20. No qualifying action surfaced for those 20 in searches of the ledger, public warnings and domestic or foreign notices, including dates outside the scoring window. Two had already been recalled. One Greenworks washer expelled a hose, but the earlier US/Canadian action covered other models. A Great Value lamp shared its certification mark with a different model in an Intertek warning. [Greenworks recall](https://www.cpsc.gov/Recalls/2021/One-Million-Greenworks-and-Powerworks-Pressure-Washer-Spray-Guns-Recalled-Due-to-Impact-Injury-Hazard-Distributed-by-Hongkong-Sun-Rise-Trading) · [Intertek warning](https://www.intertek.com/siteassets/resources/pn/2021/intertek-pn-2021-30-technical-consumer-t8-lightbulbs.pdf)

The supplied 4,788-notice ledger spans June 2011 through October 29, 2026 and omits some standalone warnings. Only actions in that archive can earn future credit. We used [documented earlier warnings](../backend/tests/fixtures/watchlist-earlier-actions.csv) to avoid calling a later recall early when CPSC had already publicly warned about that product. Restricting even prior actions to the ledger leaves the combo at 9 strict and 8 loose hits, and changes the baseline to 115 strict and 142 loose with 55 reachable notices. [CPSC warning catalog](https://www.cpsc.gov/s3fs-public/recall-data/product_safety_warning_listing.csv)

A separate search of the 393-entry warning catalog found 30 eligible links across 29 unflagged reports and no additional flagged hits. Twelve reports added a strict match and 24 added a loose match beyond their ledger labels. These supplemental results do not enter the table. [Warning decisions and official notices](../backend/tests/fixtures/watchlist-warning-audit.csv)

## Reproduce

From `backend/` with the project dependencies installed, run:

```sh
python -m scripts.watchlist_score --output /tmp/watchlist
python -m pytest -q tests/test_watchlist_score.py
```

The default uses pinned report fields, notices and adjudications in `tests/fixtures/`. It emits the summary, all 7,468 decisions, candidate links, strict positives and the random audit sample. Add `--ledger-only` for the sensitivity check or `--database` to read local incident records. [Report snapshot](data-source.md) · [Source disclaimer](../backend/cpsc360/disclaimer.txt)
