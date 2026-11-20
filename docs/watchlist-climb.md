# Exploring the 47 missed recalls

## Decision locked before the new validation run

Start with the archived, adjudicated labels from the [original benchmark](watchlist-score.md). Train on manufacturers assigned two of three hash buckets. For validation use the remaining bucket, excluding entire manufacturers that share a strict target notice with development. Keep every report in each cohort, including previously recalled products. Group assignment, candidate features and hill climbing are executable in `backend/scripts/watchlist_climb.py`.

The primary candidate (“transfer”) only admits signals that matched strict cases at three or more development manufacturers. Each step adds or removes one signal to improve distinct recalls caught minus reviews divided by 20. The queue cannot exceed the original development workload. Also lock lean and broad comparisons with review costs of 10 and 30 per distinct recall and no minimum manufacturer support. All triggers use information available by publication. Earlier same-model events arrive only after each publication day. Historical analogies use pre-2024 notices.

For this experiment, a practical improvement means at least 10% strict precision and 25% reachable-recall coverage at or below the original validation review volume. These are analyst-selected targets. Development outcomes informed the vocabulary, and earlier research already examined these years. Validation measures transfer across manufacturers in an existing retrospective dataset.

## What the 47 misses shared

There were 62 model-matched reports across the 47 notices. Forty notices had a single eligible report. Fifty-eight of the 62 reports described the notice's hazard. Four named the right product but described a different failure or an insufficiently specific one. For example, fragments in a glass of ice pointed to the later ice-bucket hazard. Shattering oven glass offered little warning of delayed gas ignition. [All 47 notices, earlier report IDs, lead times and reasons for missing](watchlist-missed-recalls.csv)

The original specific-report rule missed 39 of those 62 on injury or near-injury wording, 36 on serial/lot, 34 on failure vocabulary and six on model identification. A report can miss several requirements. Concrete failures often appeared in everyday terms, including a toy head coming off, a broken ice-bucket part in a glass, and a hose fitting flying loose. Waiting for another model-matched complaint, or for someone to be hurt, discards evidence.

## Hill-climb result

The locked primary candidate requires an identifiable structured model and one of 17 product-specific failure patterns. Examples include an accessible button battery, an igniting compact refrigerator and a failing child restraint. It requires neither a serial number nor an injury. We also offered the search the old rules, recurrence, mentions of related recalls, and similarities to pre-2024 notices. The search selected the product/failure rule alone. [All pattern definitions](../backend/scripts/watchlist_family_signals.py) · [Step-by-step selections](../backend/tests/fixtures/watchlist-climb-selection.json)

| Cohort | Queue | Reviews | Strict hits | Strict precision | Reachable recalls caught | Median strict lead |
|---|---|---:|---:|---:|---:|---:|
| Development, 4,690 reports | Original | 204 | 5 | 2.5% | 5/34 | 86 days |
| Development | Primary tuned | 175 | 34 | 19.4% | 25/34 | 143 days |
| Validation, 2,778 reports | Original | 146 | 4 | 2.7% | 2/20 | 25.5 days |
| Validation | Primary tuned | 63 | 4 | 6.3% | 2/20 | 89.5 days |
| Validation | Lean | 64 | 4 | 6.3% | 2/20 | 89.5 days |
| Validation | Broad | 67 | 4 | 6.0% | 2/20 | 89.5 days |

On validation the primary candidate caught the Baseus recall 224 days early, kept the Bugaboo high-chair recall and lost the Samsung range recall. The missed Samsung report named a recalled model but described erratic heat and a failed indicator rather than accidental knob activation. The tuned queue had five maker/type/hazard hits, versus three for the original. Nine of its 63 flags concerned previously recalled products. Median lead measures individual positive reports. The change in lead reflects a change in which cases were caught.

Across the whole retrospective dataset the primary candidate recovered **25 of the original 47 misses**, retained two of the original seven catches, and made 238 flags. Development cases dominate that result. On unseen manufacturers it recovered **one of 18 misses**, and coverage stayed at 10%. All three locked choices fell short of the 10% precision and 25% coverage targets. Most tuned vocabulary came from development misses, including several single-notice product families. The manufacturer split exposes that overfitting.

## Removing requirements, examined after validation

On the same validation reports, dropping only the serial requirement from the original specific-report rule caught 6/20 recalls with 265 reviews (8 strict hits). Dropping only the injury requirement caught 5/20 with 665 reviews (8 hits). Dropping both caught 12/20 with 1,047 reviews (17 hits, 1.6% precision). This explains why relaxing the rule buys coverage so expensively. It is an exploratory comparison.

## Reproduce

From `backend/` with project dependencies installed:

```sh
python -m scripts.watchlist_score --output /tmp/watchlist
python -m scripts.watchlist_climb fit /tmp/watchlist/reports.jsonl /tmp/selection.json
python -m scripts.watchlist_climb evaluate /tmp/watchlist/reports.jsonl /tmp/selection.json
python -m scripts.watchlist_ablation /tmp/watchlist/reports.jsonl
python -m pytest -q tests/test_watchlist_climb.py
```
