# Which reports give an early warning?

On the public snapshot through November 4, 2026, a prior hospital admission for the same make and model was the most promising low-volume watchlist signal. On held-out publications it flagged seven eligible reports. Two preceded distinct severe events. The sample is small enough that one more hit or miss matters. This rule warrants prospective testing.

## Experiment

The benchmark tested 40 lab-compatible arrival rules and all 780 two-rule combinations. These covered model bursts, injuries shared across manufacturers, prior admissions, and narrative clues with and without manufacturer recurrence. Both rules in a pair recommend watchlisting, so either can trigger review.

An eligible report has a manufacturer key and product code and has no recorded death or hospital admission. An alert counts as positive if the next recorded death or hospital admission for that manufacturer and product code is published 1–90 days later. For coverage, each manufacturer, product code and next publication date counts once, however many alerts precede it. The product code can span multiple models. Publication order measures warning before another public report. It cannot establish when the incident occurred or whether the reports share a defect.

The search maximized distinct event coverage on 13,637 eligible reports beginning January 2020, subject to three development review budgets. Ties favored more positive alerts, then fewer reviews and fewer rules. Development labels end before January 2024. A 90-day gap in scored arrivals prevents labels from crossing that boundary. History still accumulates through the gap. The holdout covers January 1, 2024 through August 6, 2026, with 12,490 eligible reports, 266 positive reports, and 45 distinct reachable next events. Arrival counts include the report itself and earlier publication days. The source supplies no timestamps to order other reports published that day.

| Development budget | Selected watchlist rules (either match) | Holdout reviews | Positive alerts | Distinct next events | Expected events at equal random volume |
|---|---|---:|---:|---:|---:|
| 1% | Five injury reports for the make/model in 90 days, or one admission for the make/model in 90 days | 57 | 2 | 2 | 1.16 |
| 5% | One make/model admission in 90 days, or near-miss wording with three manufacturer reports in 30 days | 402 | 11 | 6 | 6.49 |
| 10% | Two make/model reports in 14 days, or one manufacturer admission in 90 days | 1,014 | 76 | 11 | 12.18 |

The random column is the expected distinct coverage from sampling the same number of eligible reports uniformly without replacement. The broadest pair looked productive if measured by positive alerts alone. Its 76 positive alerts pointed to eleven events. The empty lab defaults would review zero reports.

## Leads from the individual rules

- Removing the five-injury branch from the 1% pair retained both events and reduced the queue from 57 reports to seven.
- A burst of two same-model reports within seven days, limited to models with at most three reports in 30 days, flagged 105 reports and reached four events. A simple two-report threshold over 14 days flagged 260 and reached five. The cap is worth testing where established clusters already receive attention.
- Near-miss words alone flagged 1,173 reports and reached seven events. Requiring three reports from the manufacturer in 30 days cut the queue to 395 and retained six events. The exact words are “almost,” “nearly,” “just in time,” “narrowly,” “thankfully,” and “fortunately.”

These individual-rule observations use the holdout retrospectively. A later snapshot would supply an independent check. Report volume, missing models and who chooses to report can all affect the ranking.

From the backend directory with the project environment active and the public database loaded, run `PYTHONPATH=. python scripts/benchmark_triage.py`. It prints the selected lab rule JSON for each budget and the holdout counts for every individual rule. The budgets apply to the benchmark's eligible population. Running those rules across every report in the lab also includes reports outside that population.
