# Early review of infant sleep products and expanding beads

Two single-report rules routed 26 of 70,004 public SaferProducts.gov reports for review in the snapshot ending November 4, 2026. Four reviewed product lines had an identifiable report before a subsequent recall. We selected these hazards retrospectively and inspected product descriptions and narratives to verify the links. The result measures review volume and historical lead time. Estimating precision or the fraction of all recalls detectable would require adjudicating every alert and defining a complete recall cohort. [Public incident data](https://www.saferproducts.gov/PublicSearch)

## Infant position during a fatal sleep incident

Look for an infant death, a sleep surface, and a report describing rollover or the position in which the child was found. The rule catches variation in how the product was sold or coded. It matched **16 reports** across all manufacturers, compared with 136 for age under one year and death alone. Inspectors can search the report numbers below in Explorer.

| Product and exact public report | Report published | Recall announced | Lead | Match to the announced hazard |
|---|---|---|---:|---|
| KidCo PeaPod Plus P201, `20120222-4C960-2147469921` | 2012-03-16 | 2012-11-16 | 245 days | A caregiver named model P201 and described finding an infant face down against the tent wall. CPSC identified P201, described the same side-wall position and expressly recorded the cause of death as undetermined. [Recall 13-043](https://www.cpsc.gov/Recalls/2012/suffocation-entrapment-risks-prompt-recall-of-peapod-travel-tents-by-kidco) |
| Fisher-Price Rock ’n Play, `20180122-928A0-2147393502` | 2018-09-12 | 2019-04-12 | 212 days | The caregiver described a six-month-old rolling over during a nap and dying. CPSC warned about the named product on April 5, 205 days after publication. The agency had already warned about rollover deaths across inclined sleepers on May 31, 2018. [Category alert](https://www.cpsc.gov/content/cpsc-consumer-alert-caregivers-urged-to-use-restraints-with-inclined-sleep-products) · [Named alert](https://www.cpsc.gov/Newsroom/News-Releases/2019/CPSC-ALERT-CPSC-and-Fisher-Price-Warn-Consumers-About-Fisher-Price-Rock-N-Play-Due-to-Reports-of-Death-When-Infants-Roll-Over-in-the-Product) · [Recall 19-105](https://www.cpsc.gov/Recalls/2019/Fisher-Price-Recalls-Rock-n-Play-Sleepers-Due-to-Reports-of-Deaths) |
| Boppy Newborn Lounger, `20210407-B4E12-2147364948` | 2021-05-07 | 2021-09-23 | 139 days | The product description names the lounger, and the narrative describes an infant found face down after rolling over. The October 7, 2020 class warning and public investigation already covered infant lounging pads. [Category warning](https://www.cpsc.gov/Newsroom/News-Releases/2021/CPSC-Warns-Parents-Not-to-Use-Nursing-Pillows-for-Sleep-Agency-Is-Investigating-Infant-Deaths-that-May-Be-Associated-with-Pillow-Like-Products) · [Recall 21-198](https://www.cpsc.gov/Recalls/2021/The-Boppy-Company-Recalls-Over-3-Million-Original-Newborn-Loungers-Boppy-Preferred-Newborn-Loungers-and-Pottery-Barn-Kids-Boppy-Newborn-Loungers-After-8-Infant-Deaths-Suffocation-Risk) |

Two checks expose the limits. The rule also flagged Boppy report `20191021-F3A3C-2147377052` in 2019, but its description identifies a U-shaped pillow. Assigning that alert to the Newborn Lounger would inflate its lead time. In the other direction, the rule yielded no verified Kids II Rocking Sleeper match before its April 26, 2019 recall, even though CPSC described five fatalities in the recall notice. [Kids II recall 19-112](https://www.cpsc.gov/Recalls/2019/Kids-II-Recalls-All-Rocking-Sleepers-Due-to-Reports-of-Deaths)

## Hospital admission after an expanding bead was swallowed

Carry forward a mechanism from an older recall across brands. In December 2012 CPSC recalled Dunecraft water-absorbing toys after an infant needed surgery for intestinal obstruction. The rule looks for a hospital admission, an ingestion, an obstruction or intervention, and an expanding-bead description. It produced **10 reports** versus 33 with the product-description terms alone (searched across the three text fields below). An August 27, 2020 report, `20200507-98929-2147372477`, described surgery to remove beads from a child's small intestine. Its product was Orbeez. This is independent evidence for the mechanism across brands. [Dunecraft recall 13-071](https://www.cpsc.gov/Recalls/2012/dunecraft-recalls-water-balz-skulls-orbs-and-flower-toys-due-to-serious-ingestion)

On **November 28, 2022**, report `20221108-4B613-2147352855` identified Buffalo Games and the Chuckle & Roar Ultimate Water Beads. It described ingestion, blocked small intestine, and hospitalization. A second submission published the next day described a closely similar episode. Treat the pair as one product signal pending verification of distinct patients. Another Chuckle & Roar report in January concerned a different sensory-bin kit. Product and mechanism inspection prevent counting it toward the Ultimate Water Beads recall. [SaferProducts.gov reports](https://www.saferproducts.gov/PublicSearch)

The November report preceded the **September 14, 2023 recall by 290 days** and a named commissioner's public statement by 289 days. CPSC reported that sales ended in November 2022, a Maine child required surgery that month, and a Wisconsin infant died in July 2023. Staff had also raised the wider hazard with ASTM in June 2023. These records support flagging the *specific kit* ahead of the recall and before the later reported death. They leave the dates of first manufacturer and agency recognition unresolved. [Product recall 23-286](https://www.cpsc.gov/Recalls/2023/Buffalo-Games-Recalls-Chuckle-Roar-Ultimate-Water-Beads-Activity-Kits-Due-to-Serious-Ingestion-Choking-and-Obstruction-Hazards-One-Infant-Death-Reported-Sold-Exclusively-at-Target) · [Commissioner statement](https://www.cpsc.gov/About-CPSC/Commissioner/Richard-Trumka/Statement/Water-Beads-Can-Cause-Intestinal-Obstruction-and-Lead-to-Death-Get-Them-Out-of-Your-Home) · [CPSC staff letter to ASTM](https://www.cpsc.gov/s3fs-public/Letter-to-ASTM-on-Expanding-Water-Beads-6-20-23.pdf)

## Reproduce the review queue

Run this PostgreSQL query against the project's public snapshot. Each report is eligible on its publication date, using the product fields, severity, and narrative in the current snapshot. Brand, recall number, future reports, and company responses do not enter the rules. Missing age, missing severity, and other wording can cause misses.

```sql
SELECT report_no, publication_date, product_type, brand, model,
       CASE WHEN severity = 'Death' THEN 'Infant position' ELSE 'Bead obstruction' END AS signal
FROM source.incident
WHERE publication_date <= DATE '2026-11-04' AND (
  (victim_age = 0 AND severity = 'Death'
   AND incident_description ~* '(rolled over|face down|face-down|on (his|her) stomach)'
   AND concat_ws(' ', product_type, product_description, model)
       ~* '(bassinet|cradle|sleeper|lounger|pillow|crib|play yard)')
  OR
  (severity = 'Injury, Hospital Admission'
   AND incident_description ~* '(swallow|ingest)'
   AND incident_description ~* '(intestin|bowel|obstruct|surg)'
   AND concat_ws(' ', product_description, incident_description, model)
       ~* '(water ?bead|expanding bead|expandable bead|gel bead|hydrogel bead)')
)
ORDER BY publication_date, report_no
```
