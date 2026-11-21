# Early warnings in exercise equipment

## A known failure mechanism across three later products

In June 2012 CPSC announced a recall of a subset of Bowflex SelectTech 1090 dumbbells after weight selection could leave plates unsecured. The public snapshot already contained a June 7, 2011 report, `20110314-04C0A-1170739`, identifying that model and describing plates falling during lifting, including one onto the reporter’s foot. The report predates the affected units’ stated retail sales period and lacks a serial number. It establishes a historical mechanism to look for across brands. It cannot identify a unit in the 2012 recall. [CPSC recall 12-194](https://www.cpsc.gov/Recalls/2012/nautilus-recalls-bowflex-dumbbells-due-to-injury-hazard)

The resulting review rule looks for one weight-lifting or exercise-equipment report that names a dumbbell, references a weight or plate, and describes separation. A watchlist can act on the first such report even if the reporter avoided injury or another manufacturer experienced the earlier defect. All three rows below matched the rule on their public publication date. The recall notices supply the later model and hazard checks. The dates of agency discovery for these three recalls are unknown.

| First matching public report for the identified model | Product and evidence available in the report | Recall announcement | Days earlier |
|---|---|---|---:|
| 2022-11-18 · `20221028-27F09-2147353069` | NordicTrack iSelect NTSAW23020.0. The reporter described a misaligned sliding lock and plates falling during lifting. Both model and mechanism match. | 2024-02-01 · [CPSC 24-102](https://www.cpsc.gov/Recalls/2024/iFIT-Recalls-NordicTrack-50-LB-iSelect-Voice-Controlled-Adjustable-Dumbbells-Due-to-Impact-Hazard) | 440 |
| 2023-09-29 · `20230913-02008-2147345235` | ProForm PAMSDB20. The reporter described a sheared bolt, displacement of the selector, and plates striking their head. The model and separating plates match. CPSC’s notice does not identify the bolt as the cause. | 2024-07-25 · [CPSC 24-310](https://www.cpsc.gov/Recalls/2024/iFIT-Recalls-ProForm-50-LB-Adjustable-Dumbbells-Due-to-Impact-Injury-Hazard) | 300 |
| 2024-04-16 · `20240321-6633B-2147340223` | FitRx model 9034, serial KK23289034. The narrative describes a weight falling out on pickup. Both identifiers match the recall, despite a misspelling of “dumbbell” in the narrative. | 2025-03-20 · [CPSC 25-184](https://www.cpsc.gov/Recalls/2025/Tzumi-Electronics-Recalls-SmartBell-XL-Quick-Select-Adjustable-Dumbbells-Due-to-Impact-Injury-Hazard-Sold-Exclusively-at-Walmart-com) | 338 |

The query returned **35 reviews** among 618 reports in the two eligible product types, from 62,695 total public reports after the 2012 notice through November 4, 2026. That includes reports published after recalls. The vocabulary was assembled retrospectively. The three case matches demonstrate possible lead time for these products, and the 35 reviews measure workload. Estimating predictive accuracy would require independent review of all alerts and a separately defined recall cohort. [SaferProducts public reports](https://www.saferproducts.gov/PublicSearch)

```sql
SELECT report_no, publication_date, product_type, manufacturer_name, model
FROM source.incident
WHERE publication_date > DATE '2012-06-07' AND publication_date <= DATE '2026-11-04'
  AND product_type IN ('Weight Lifting (Activity, Apparel or Equipment)', 'Exercise Equipment')
  AND incident_description ~* '(dumbbell|dumbell|dumb bell|smartbell)'
  AND incident_description ~* '(plate|weight)'
  AND incident_description ~* '(fell off|fall off|falls off|fallen off|fell out|fall out|falls out|came off|coming off|detached|dislodg|sheared off)'
ORDER BY publication_date, report_no;
```

Using only the original 2011 report's two release phrases in the final SQL predicate, `(fall off|fall onto)`, produced five reviews in the same interval. It caught the NordicTrack iSelect report. The broader wording recovered the ProForm and FitRx models at the cost of 30 additional reviews. The original wording therefore provides a historically available starting point for at least one later model, while the wider vocabulary benefits from hindsight.

Two examples illustrate how to review a match. Report `20250322-E3014-2147332405` describes dumbbells falling from a retail display, a different mechanism. Report `20210127-D3A5F-2147366234` describes loose plates on a NordicTrack Speedweight NTSAW11016. Counting it as an earlier iSelect alert would conflate different models. Exact report numbers can be looked up in Explorer. [SaferProducts public reports](https://www.saferproducts.gov/PublicSearch)

## One severe report versus waiting for a cluster

Peloton’s Tread+ illustrates a second rule and a limit of the public clock. CPSC staff’s settlement chronology describes reports to Peloton beginning in December 2018 and a formal Peloton filing with CPSC on March 4, 2021. The agency’s April 17 stop-use warning followed an already announced investigation. CPSC and Peloton announced the recall on May 5. A different Tread model had a separate console-detachment recall that same day. [Settlement agreement, paragraphs 7–14 and 23–25](https://www.cpsc.gov/s3fs-public/PelotonInteractiveIncProvSettlementAgreementandOrder23C0001p_0.pdf), [CPSC warning and recall 21-128](https://www.cpsc.gov/Recalls/2021/Peloton-Recalls-Tread-Plus-Treadmills-After-One-Child-Died-and-More-than-70-Incidents-Reported)

A brand-independent rule for severe treadmill entrapment in young children produced **one alert among 70,004 public reports**. Report `20210213-97C35-2147365910`, submitted February 13 and published March 18, 2021, identifies a three-year-old hospitalized after being trapped under a Tread+. The structured model says “Tread,” but the product description and narrative both identify the Plus. The public alert comes **30 days before the stop-use warning**, **48 days before recall**, and **14 days after** Peloton's documented filing with CPSC. A second relevant report, `20210418-5CD5B-2147364673`, describes a five-year-old pulled underneath and records first aid. Its May 4 publication already follows the stop-use warning. Requiring two corroborating reports of children in this pair would forfeit the pre-warning lead. [SaferProducts public reports](https://www.saferproducts.gov/PublicSearch), [CPSC warning and recall](https://www.cpsc.gov/Recalls/2021/Peloton-Recalls-Tread-Plus-Treadmills-After-One-Child-Died-and-More-than-70-Incidents-Reported)

```sql
SELECT report_no, publication_date, manufacturer_name, model
FROM source.incident
WHERE publication_date <= DATE '2026-11-04'
  AND victim_age <= 5
  AND severity IN ('Death', 'Injury, Hospital Admission')
  AND incident_description ILIKE '%treadmill%'
  AND incident_description ~* '(trapped|pinned|pulled under|sucked under|caught under)'
ORDER BY publication_date, report_no;
```
