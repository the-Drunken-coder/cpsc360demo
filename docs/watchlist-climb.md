# Exploring the 47 missed recalls

## Decision locked before the new validation run

Start with the archived, adjudicated labels from the [original benchmark](watchlist-score.md). Train on manufacturers assigned two of three hash buckets. For validation use the remaining bucket, excluding entire manufacturers that share a strict target notice with development. Keep every report in each cohort, including previously recalled products. Group assignment, candidate features and hill climbing are executable in `backend/scripts/watchlist_climb.py`.

The primary candidate (“transfer”) only admits signals that matched strict cases at three or more development manufacturers. Each step adds or removes one signal to improve distinct recalls caught minus reviews divided by 20. The queue cannot exceed the original development workload. Also lock lean and broad comparisons with review costs of 10 and 30 per distinct recall and no minimum manufacturer support. All triggers use information available by publication. Earlier same-model events arrive only after each publication day. Historical analogies use pre-2024 notices.

For this experiment, a practical improvement means at least 10% strict precision and 25% reachable-recall coverage at or below the original validation review volume. These are analyst-selected targets. Development outcomes informed the vocabulary, and earlier research already examined these years. Validation measures transfer across manufacturers in an existing retrospective dataset.
