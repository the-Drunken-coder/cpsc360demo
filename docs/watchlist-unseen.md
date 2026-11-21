# Held-out years at the incumbent review budget

## Protocol

Develop on the adjudicated publications from 2020–25. Leave 2016–17 and 2018–19 to an independent reviewer. No blind-period outcome, case list or score may inform the challenger. Lock a single schedule before running it on either block. The comparison is a retrospective transfer test across report years, not a simulation of training a model in 2016.

Success means catching more distinct, model-matched public actions than the incumbent in the pooled blind blocks with no additional reviews. Also report both blocks individually, the previous weekly queue, review dates, gains and losses. Use the archived CPSC notice ledger, 1–365 days from publication, a strictly future action on the actual review day, and prior-action exclusions. A report shared across queues gets the same label. Unknown outcomes and missing model links limit inference. Stop selection before opening either block.

Also run the same frozen challenger on 2014–15 as a separate replication, and report it regardless of the primary result. Neither competing models nor repeated measurements on the blind years will be used to select the headline.

We tested 142 combinations with the classifier trained on the other two development blocks each time. Retain at least 75% of incumbent coverage on the block that informed the incumbent (2024–25), then maximize the weaker of the 2020–21 and 2022–23 gains. Break ties by combined gain there, recent coverage, then simplicity. The selected scores gained one and five actions in those two development blocks and lost four in 2024–25. A preliminary grid that prioritized worst absolute gain across all three selected a zero-gain comparator.

Each Sunday the challenger earns as many slots as the incumbent flagged reports that week. It considers this week's reports and the previous week's backlog. Rank by four times the eighth power of the classifier's arrival-time score percentile, plus narrative/acquisition evidence, plus three per previous same-model report in 120 days (maximum two), plus five for an incumbent flag. Once a maker/model gets a review, suppress its duplicates for 120 days. Break ties by hash of report ID. Train the final classifier on all three development blocks. It sees product categories and incident concepts, with names and model codes used only for identity and recurrence.

The original development search held out publication years. One recall (22153) had earlier reports in both the 2020 and 2022 blocks. Three (24110, 24335, 24377) crossed the 2022 and 2024 blocks. The weekly detector’s 2022–23 check therefore reused some target recalls from its development years. Neither queue caught any of those three in that check. Across the four earlier blocks from 2012 through 2019, none of the verified reachable notices appeared in classifier training labels.

Repeating all 142 combinations after excluding every training report linked to a held-out recall selected the same weights and development gains (+1, +5, −4). This sensitivity check leaves the frozen challenger and its headline results unchanged. Omit `--original-folds` in the reproduction command to run this check.

## Additional replication decision

After seeing the 2016–19 comparison, select the **unchanged weekly queue** from commit `9f2722f` for a separate 2012–13 check, against the unchanged incumbent. This is a follow-up selection, not a change to the frozen primary challenger. No 2012–13 outcomes informed this decision. Run the previously fixed protection variant and the supervised challenger there for comparison only. Report the result whichever method wins.

## Results on years excluded from tuning

The frozen weekly queue caught five of 62 verified reachable U.S. notices on the 2016–19 primary test. The original caught three and the new classifier caught two. All three spent 339 reviews. Weekly retained all three original catches. Its two extra catches came from the same two-year block, and neither replication showed an advantage over the original.

| Publication years | Reports | Verified reachable notices | Reviews per queue | Original catches | Weekly catches | Classifier catches |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2016–17, primary | 7,922 | 27 | 123 | 3 | **5** | 1 |
| 2018–19, primary | 6,547 | 35 | 216 | 0 | 0 | **1** |
| 2014–15, replication | 9,284 | 22 | 116 | 2 | 2 | 1 |
| 2012–13, follow-up replication | 12,409 | 29 | 108 | 0 | 0 | 1 |

Across all six two-year blocks from 2012–23 that were excluded from **weekly** tuning, weekly won one block, tied four and lost one. It caught 11 notices versus 10 for the original at 831 reviews each. Excluding the Kidde match makes that comparison 10–10. The 2020–23 blocks were used to develop the new classifier and cannot validate it. [Earlier two block results](watchlist-budget.md)

Across the primary years, each catch came from one reviewed report. Weekly yielded five model matches in 339 reviews (1.5%), versus three in 339 (0.9%) for the original. Of the three cases both caught, waiting until Sunday cost three or four days apiece. The classifier uniquely flagged a Whirlpool cooktop 17 days early. Its gains on two development blocks did not transfer to the pooled primary test. [All credited reports, review dates and leads](watchlist-unseen-hits.csv)

- **Cuisinart, 149 days early.** The consumer described a food-processor blade breaking at its rivets and leaving metal in food. The weekly queue picks up fragments in food across appliances, a mechanism already in a 2015 recall. The later Cuisinart notice describes the same failure. [CPSC notice 17-050](https://www.cpsc.gov/Recalls/2017/Cuisinart-Food-Processors-Recalled-by-Conair)
- **Kidde, 60 days early.** The report described a failed CO test. The alarm type, manufacture date and model matched after treating a “1” in the reported model as an “I.” The notice identifies a narrower end-of-life alarm failure. The detector also uses a 2022 alarm precedent. Dropping this less conclusive case leaves weekly ahead 4–3 on the primary test. [CPSC notice 17-031](https://www.cpsc.gov/Recalls/2017/Kidde-Recalls-Combination-Smoke-CO-Alarms)
- **2012–15 replications.** Weekly and original caught the same two notices in 2014–15 and none in 2012–13. Protecting the first original alert also caught zero in 2012–13. The classifier caught one in each block. The 2012 Bugaboo report named the recalled stroller but described a different defect. Japan had already announced the carry-handle recall by the queue's review date. Its 23-day lead applies only to the U.S. notice. [Japan’s recall](https://www.meti.go.jp/product_safety/recall/file/121217-1.html) · [U.S. recall](https://www.cpsc.gov/Recalls/2013/bugaboo-recalls-strollers-due-to-fall-and-choking-hazards)

Independent reviewers checked candidate model links across the cohorts and broadened searches for the selected queues using names, model prefixes, aliases and product codes. They excluded incompatible models, parts and known prior U.S. actions. For example, a Ryobi charger looked like a hit until the notice specifically excluded its nine-digit part number. Reachable counts are lower bounds from verified links to the 4,788-notice ledger. A match credits a covered model even when the incident does not establish the same defect. Historical reports and incomplete standalone-warning coverage limit the test. All eight report years were outside tuning, but come **before** development in calendar time.

## Reproduce

Run from `backend/` with the incident database loaded and project dependencies installed. The committed selection is from `deb5c4e`. The follow-up choice for 2012–13 is from `920ceaf`.

```sh
python -m scripts.watchlist_score --output /tmp/watchlist
OPENBLAS_NUM_THREADS=1 python -m scripts.watchlist_blind fit --original-folds --modern /tmp/watchlist/reports.jsonl --output /tmp/selection.json
cmp /tmp/selection.json tests/fixtures/watchlist-unseen-selection.json
OPENBLAS_NUM_THREADS=1 python -m scripts.watchlist_blind blind --modern /tmp/watchlist/reports.jsonl --output /tmp/watch-blind-out
python -m scripts.watchlist_blind_results /tmp/watch-blind-out
```

The final command returns verified reachable notice IDs, review counts and each credited report/notice pair with days from actual review to U.S. announcement. Model-link decisions and any identified earlier U.S. public action are in the three review CSVs in `backend/tests/fixtures/`.
