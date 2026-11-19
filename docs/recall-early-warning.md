# Replaying CPSC recall signals from public incident reports

A working rule for the review queue is to flag a specific failure mode already documented in an older recall when it appears in another product. Use a second matching report to prioritize follow-up. Requiring two reports before anyone reads the first one loses some of the clearest near misses. Three companion studies trace this tradeoff in [children's products](recall-child-products.md), [ranges](recall-appliances.md) and [exercise equipment](recall-mechanical.md).

## Which signals to try first

| Review trigger | Observed queue | Strongest historical check |
|---|---:|---|
| A plate or weight separates from an adjustable dumbbell | 35 reports after the 2012 Bowflex notice | Three later models matched. Using only two release phrases present in a 2011 complaint cut the queue to five and still identified NordicTrack 440 days before recall. |
| Hospital admission after ingestion of expanding beads, with obstruction or intervention | 10 reports | An earlier Dunecraft recall documented the mechanism. A report naming the Chuckle & Roar kit appeared 290 days before recall and before a later reported fatality. |
| Cooker lid or hot contents eject | 52 reports | A no-injury report identified a listed Bella model. Two Ninja reports implicated different models within nine days. |
| Two reports of knob contact and unintended activation on the same maker and range product code | 54 threshold-crossing alerts | Restarting after the Samsung recall still flagged LG 163 days before its recall. Two reports naming listed LG models followed. |
| Infant fatality with position and sleep-surface evidence | 16 reports | Three product lines flagged 139–245 days before recall. The rule missed Kids II, and earlier class-wide CPSC warnings already covered two flagged product families. |
| Severe child entrapment under a treadmill | 1 report | The Tread+ report preceded the stop-use warning by 30 days but followed the firm's CPSC filing by 14 days. |

Queue sizes count different units and windows as described in the companion studies. For a watchlist, the strongest evidence of transfer is a mechanism described before the target product came to attention, a report that identifies the product, and a workload measured across all brands. When the first report lacks a model, the range example supports retaining the lead and looking for later identifying evidence. Counting the elapsed time to announcement as time saved by CPSC would require a discovery date and an investigation timeline that these public reports generally cannot supply.

## Pressure cookers as a transfer test

Before the first report in this database, CPSC and QVC had announced a recall involving a pressure-cooker lid opening while pressurized and expelling hot contents. That earlier case supplied a reason to look across manufacturers for unexpected lid movement and ejection of hot food. Brand, model, injury severity and future recall status play no part in the two mechanism rules. [CPSC and QVC recall](https://www.cpsc.gov/Recalls/2006/electronic-pressure-cookers-sold-by-qvc-recalled-due-to-burn-hazard?language=en)

The replay uses all 70,004 reports in the loaded snapshot, June 2011 through November 4, 2026. It found 179 reports with the public product type “Pressure Cookers or Canners.” An alert can fire on publication. The first rule requires “lid” and an ejection expression. The second requires an ejection expression and wording about hot contents. The repeat rule requires a mechanism hit for the same manufacturer on an earlier publication date within 365 days. The exact text lists are in the [replay](../backend/scripts/replay_cooker_recalls.py). Two reports can still describe one incident, and reporters can use these words for ordinary venting or another kind of failure.

| Rule | Reviews across the snapshot | Reviewed pre-recall reports linked to a listed model and compatible failure in the five selected recalls |
|---|---:|---|
| Every cooker | 179 | Bella and Ninja |
| Hospital admission | 11 | None |
| Lid and ejection | 37 | Bella and Ninja |
| Ejection and hot contents | 31 | Ninja |
| Either mechanism | 52 | Bella and Ninja |
| Repeat mechanism at maker | 18 | Ninja |

These are counts of queued reports, including reports after recalls. We matched the announcement and report manually using model, brand, failure and publication date. The set of five later recalls was selected retrospectively. Alerts outside the adjudicated cases remain unlabeled. The experiment measures workload and lead on these cases. It cannot estimate recall prediction precision or population-wide sensitivity.

### Bella and Ninja

- **Bella, 1,903 days before recall.** On May 25, 2018, report `20180123-B69D6-1728384` identified Bella stovetop model JY-PC20US-5P. The lid popped off and the contents spilled when the consumer moved the cooker. The structured severity recorded no injury. CPSC listed that exact model in the August 10, 2023 refund recall for lids unlocking and hot contents escaping. The report supports a review of lid retention. It does not establish why the lid released. [CPSC recall and model list](https://www.cpsc.gov/Recalls/2023/Sensio-Recalls-Bella-Bella-Pro-Series-Cooks-and-Crux-Electric-and-Stovetop-Pressure-Cookers-Due-to-Burn-Hazard)
- **Ninja, 1,871 days before recall and corroboration nine days later.** On March 17, 2020, report `20200210-472E0-2147374912` identified OP305CO, hot water spraying bystanders, and an emergency-department-treated burn. This first alert identifies ejection and injury, with the lid mechanism uncertain. On March 26, report `20200221-1E546-1955848` described a different incident involving an OP301, a pressure cycle, lid ejection and burns. Manufacturer-level corroboration caught both models. Waiting for another identical model would have missed the pair. CPSC announced the OP300-series repair on May 1, 2025. A FOIA response withheld the investigation records, leaving the agency's first awareness date unresolved. [CPSC recall](https://www.cpsc.gov/Recalls/2025/SharkNinja-Recalls-1-8-Million-Foodi-Multi-Function-Pressure-Cookers-Due-to-Burn-Hazard-Serious-Burn-Injuries-Reported) · [CPSC FOIA response](https://www.cpsc.gov/s3fs-public/25-F-00486-FOIA-Request-Description-and-Response.pdf)

### Three recalls without a verified pre-announcement hit

- **Crock-Pot.** Report `20190107-3A6C8-2147383375` names recalled model SCCPPC600-V1 but describes a fire in an unplugged cooker. It would be a misleading early hit. A same-model lid-and-soup report was published January 5, 2021, after the November 24, 2020 announcement. A released Section 15(b) initial report dated August 22, 2018 refers to earlier August 6 correspondence and a compliance officer's request. Here the Commission had evidence well before the public report we could match. [Recall](https://www.cpsc.gov/Recalls/2021/Crock-Pot-6-Quart-Express-Crock-Multi-Cookers-Recalled-by-Sunbeam-Products-Due-to-Burn-Hazard) · [FOIA case records, pages 185–186](https://www.cpsc.gov/s3fs-public/FOIA-Request-21-F-00610-Part-1-of-4-Agency-Response-and-Records-Redacted.pdf?VersionId=Pjv2jrOeKINA.lFP7Xqp0_sYS7YhSAwq)
- **Insignia.** The October 26, 2023 recall linked ejection to incorrect fill markings. The exact-model hot-soup report `20250207-94B8A-2147333377` was published February 27, 2025. It provides no early credit. [CPSC recall](https://www.cpsc.gov/Recalls/2024/Best-Buy-Recalls-Insignia-Pressure-Cookers-Due-to-Burn-Hazard)
- **Ambiano.** Report `20241016-43D9E-2147335930` identifies 6L-PC before the October 9, 2025 recall, but describes a melting power connection. The recall concerns premature lid opening. Counting all burns on that model would conflate two different hazards. [CPSC recall](https://www.cpsc.gov/Recalls/2026/Tempo-USA-Recalls-Ambiano-Electric-Pressure-Cookers-Due-to-Serious-Burn-Hazard-Multiple-Burn-Injuries-Reported-Sold-at-ALDI)

## Reproduce and interpret

From the backend directory, use the project Python environment and run `PYTHONPATH=. python scripts/replay_cooker_recalls.py --alerts`. The output includes the publication dates, report numbers, manufacturers, models, and matching rules for inspection in Explorer. The case labels credit only the reviewed records above. False negatives can arise from other product codes, missing models or different wording. The source is a current snapshot ordered by original publication date. Later edits to a report may be reflected in its text. [Snapshot documentation](data-source.md) · [SaferProducts.gov public search](https://www.saferproducts.gov/PublicSearch)
