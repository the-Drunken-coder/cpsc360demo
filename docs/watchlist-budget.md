# More recall coverage at the same review budget

The tuned watchlist missed 18 of 20 reachable recalls in its previous manufacturer split. All 30 model-matched reports behind those 18 missed **every** one of its 17 product/failure patterns. Twenty-five supplied a structured model. Twenty-four described the eventual hazard, across 17 recalls. Removing the model requirement alone would recover zero. Sixteen recalls had just one eligible public report. [Notice-by-notice audit](watchlist-18-misses.csv)

Six notices involved a falling or unstable load, three toy choking, two component release, two vehicle control, two electrical protection, one unintended activation and one steam leak. The last involved a gas range whose report described shattered glass and whose recall concerned delayed ignition. Examples of actionable wording included a tractor brake linkage breaking, a toddler figure losing its head and a pressurized steam connection leaking. A prior public manufacturer callback in the 3D-printer case also illustrates that lead to a CPSC notice can exceed lead to a public company action.

## What changed

Keep the earlier model-plus-failure detector as the source of review slots. Each of its flags earns one slot. Every Sunday, rank that week's candidates using observed component failures, explicit product identity and past frequency of the failure pattern. An unused slot carries forward. Candidates expire at the end of their week. Within 30 days, suppress a repeat from the same manufacturer if all its matching patterns already received review. This preserves the *cumulative* review budget on any stream; a single week can spend banked slots. Charge lead time to Sunday, even when the report appeared earlier that week. No reviewed action on or before Sunday earns a hit.

Seven new predicates came from inspecting these misses. Eleven others came from historic recall descriptions without viewing this cohort. We tried a fixed allowance of one review per 45 arrivals, then a workload tied to the incumbent detector. We tested recurrence intervals of 30–365 days, different weights for incumbent flags and frequency-based ranking. A flat allowance improved the small cohort but reduced full-corpus coverage to 18/54. Giving the incumbent extra priority also lost opportunities. We selected the 30-day interval with frequency-based ranking and no extra incumbent bonus. These comparisons informed the selection and are exploratory. [Queue implementation](../backend/scripts/watchlist_queue.py) · [Historical mechanism predicates and notice IDs](../backend/scripts/watchlist_prior_patterns.py)

## Recent replay

| Queue and stream | Reviews | Strict positive reports | Reachable recalls caught | Median days early |
|---|---:|---:|---:|---:|
| Previous queue, former validation manufacturers | 63 | 4 | 2/20 | 89.5 |
| New queue, same manufacturers | 63 | 5 | 5/20 | 53 |
| Previous queue, all 2024–25 reports | 238 | 38 | 27/54 | 141.5 |
| New queue, all 2024–25 reports | 238 | 33 | 30/54 | 137 |

The three additional catches in the isolated cohort were Fisher-Price toddler figures, John Deere tractors and FitRx dumbbells. It retained Baseus and Bugaboo. In the full stream the new rule gained six notices and lost three. Precision fell from 16.0% to 13.9% as more reviews went to distinct failures. The two replays have different competition for weekly slots: if all reports share one queue, the former validation manufacturers account for 66 of its 238 reviews and 6 of its 30 catches.

## Reproduce

From `backend/` with the project dependencies installed:

```sh
python -m scripts.watchlist_score --output /tmp/watchlist
python -m scripts.watchlist_queue_replay /tmp/watchlist/reports.jsonl
python -m pytest -q tests/test_watchlist_queue.py
```

## Independent earlier-period checks

Commit `9f2722f` locked the selection before looking at the 2022–23 and 2020–21 outcomes. These are retrospective tests of the locked queue. Several source mechanisms were published after these earlier periods, so these checks measure transfer across incident cohorts rather than what could actually have been built at the time.

In 2022–23, both queues reviewed 146 of 7,407 reports and caught the same 2 of 37 verified reachable notices: the Boon B731 high chair and Aiper Elite Pro pool vacuum. Batching delayed both hits by four days. We reviewed 164 candidate strict links across the whole cohort, checked 44 additional model substring matches and broadened the model search for both queues. The denominator is the set we could verify. Both queues also preceded a standalone HTRC charger warning outside the fixed notice ledger. It earns neither queue extra credit.

The 2024–25 stream had a peak of nine weekly reviews for either queue. The weekly queue never exceeded the incumbent in any week in that replay. Only the cumulative budget is guaranteed by design.

For earlier reports, run `python -m scripts.watchlist_historical_check --start-year 2022` or use `2020` against the project incident database. The script replays the queue on all reports and reads the archived pair adjudications.

Changing only the tie-break order 20 times returned 28–30 notices on the full recent cohort, versus 27 previously. The smaller cohort returned 4–5 versus 2 previously. The reported score uses the original, unseeded ordering. To reproduce other orderings, use `--tie-seed '0:'` through `'19:'` in the recent replay.

The 2020–21 check reviewed 122 of 7,415 reports in each queue. The incumbent caught three notices and the locked queue caught two. Both caught two child-resistant packaging recalls for lidocaine products. Only the incumbent caught the Costco solar LED market umbrella. A single extra catch matters when the positive count is this small. The recent gain did not replicate across the two earlier periods.

After viewing the earlier results, we tried a more conservative alternative. Review the first incumbent alert immediately, suppress repeat maker/pattern alerts within 30 days, and spend only the freed slots on other failures. On the 18-miss cohort it caught 4/20 at 63 reviews. Across the full recent population it caught 27/54 at 238 reviews, equal to the incumbent. This is a post hoc comparison.

The 2020–21 verified denominator was 36 notices. The conservative alternative retained all three incumbent catches with 122 reviews. Because we designed that alternative after seeing the umbrella miss, retaining it is an exploratory result.
In 2022–23 the conservative version also retained both incumbent catches with 146 reviews. Across the two older cohorts neither alternative found an additional verified recall.
