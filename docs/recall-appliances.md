# Range knobs that activate a burner on contact

A pair of reports describing the same physical sequence gave a watchlist signal several years before two electric range recalls. A person brushed or leaned against a knob, an element switched on unnoticed, and something left on the cooktop heated. Across the public snapshot through November 4, 2026, a two-report threshold raised 54 alerts across 20 manufacturer and product-code combinations. Reviewers would need to read the paired reports to determine whether they describe the same failure. [SaferProducts.gov bulk data](https://www.saferproducts.gov/SPDB.zip)

| Recall | First matching public report | Second report that triggered review | Lead to announcement |
|---|---|---|---:|
| Samsung electric, August 8, 2024 | October 20, 2014 · `20140829-298C0-1426008` | October 23, 2014 · `20140930-324D0-2147440506` | 3,577 days |
| LG electric, February 6, 2025 | April 11, 2016 · `20160320-2FB8B-2147420810` | December 5, 2016 · `20161107-5672D-2147411020` | 2,985 days |
| Best Buy Insignia gas, July 9, 2026 | No matching Best Buy pair | No alert | — |

The first Samsung caller described brushing the front knobs and burning a cover. The second described a workman's drill case melting and a towel igniting. Both records identify base model NE58F9500SS, although the first stores it in the serial-number field and neither supplies the /AA suffix listed in the recall. The notice includes about 1.12 million ranges and offers knob locks or covers. Samsung had already received complaints dating back to 2013. [Samsung recall 24-335](https://www.cpsc.gov/Recalls/2024/Samsung-Recalls-Slide-In-Electric-Ranges-Due-to-Fire-Hazard)

Both LG reports name LDE4413ST and give different serial numbers. In April, the consumer described a towel and groceries igniting after an apparent knob bump. In December, a consumer described a glass dish shattering after someone leaned against a knob. LG's later notice lists that model with serial-number restrictions and supplies a warning label and instructions for using the control lock. These narratives and model fields support the linkage. They do not establish membership in CPSC's official incident tally. [LG recall 25-126](https://www.cpsc.gov/Recalls/2025/LG-Recalls-Electric-Ranges-Due-to-Fire-Hazard)

Insignia provides a check on how far this approach transfers. The recall covered two gas ranges and the notice cites one report to the firm. The three pre-announcement range records found under Best Buy, Insignia, or the exact recall model codes concern other model numbers and other failures. A database of public complaints cannot guarantee coverage of manufacturer reports. [Insignia recall 26-606](https://www.cpsc.gov/Recalls/2026/Best-Buy-Recalls-Insignia-Gas-Ranges-Due-to-Risk-of-Serious-Injury-from-a-Fire-Hazard)

## Earlier agency work

CPSC staff presented gas-range accidental activation data at an April 17, 2020 standards meeting. The electric-range alerts in the table predate even that public class-level milestone by 2,003 and 1,229 days, respectively. A later joint gas and electric group reviewed CPSC data across manufacturers. In January 2025 staff described 455 in-scope incidents in an internal system covering multiple sources. Announcement lead times cannot date internal recognition, establish that CPSC missed these reports, or say how soon a recall could have been justified. [April 2020 meeting log](https://www.cpsc.gov/s3fs-public/4-17-2020%20%20CSA%20Front%20Mounted%20Burner%20Control%20Task%20Force.pdf) · [January 2025 meeting log](https://www.cpsc.gov/s3fs-public/2025-01-14-independent-joint-range-knob-working-group-Log-of-Meeting.pdf)

## Cross-manufacturer check after the Samsung announcement

Starting with **empty history** the day after the Samsung recall, the rule flagged LG electric on August 27, 2024, 163 days before LG's announcement. The two reports published that day describe accidental knob contact (`20240808-056C3-2147337401`, `20240809-5DEA7-2147337365`). Neither supplies an exact listed model. On September 5 and 6 two more matches supplied listed LG model codes LSE4613BD and LSE4611ST (`20240818-444D6-2147337107`, `20240816-66F20-2147337152`). The first includes an additional revision suffix. This replay required eight alerts across all manufacturers from 52 text matches and 389 range reports up to the day before the LG announcement. Publicity from Samsung's recall could have increased reporting. This tests a plausible transfer date using retrospectively chosen language.

## Reproduce the alerts

The query uses public narratives and waits for a second distinct report for the same manufacturer and range product code within an inclusive 365-day window. It uses the current snapshot's narrative as of the report's publication date, reads all manufacturers and severities, and breaks same-day ties by report number. An alert fires when exactly one earlier matching report remains in the window. Increasing the threshold to three produced 40 alerts across 14 combinations, pushing Samsung's first alert to April 15, 2015 and LG's to December 30, 2016. For that variant use lag offsets 2 and 3 in place of 1 and 2. In the query below the 9,952 range reports yielded 555 narrative matches. The remaining alerts have not all been adjudicated, so the workload is measurable while precision is unknown.

A generic fire-language comparison produced 3,866 matches and 123 alerts. Its first Samsung and LG electric alerts both appeared in 2012, before the affected ranges went on sale. The four reports described other models, including a Samsung with rear-panel smoke and an LG in a self-cleaning cycle. Counting an early manufacturer alert as a recall prediction would credit the wrong failure. To reproduce this comparison, replace the three narrative tests in `matches` with `incident_description ~* '\m(fire|flame|smoke)\w*'`.

For the transfer check, restrict the first CTE to publication dates strictly after August 8, 2024 and strictly before February 6, 2025. To retrieve narratives, look up the two report numbers returned by each alert in Explorer. Free-text terms can occur in separate sentences describing different events, and a changed manufacturer name or product code can split a genuine series.

```sql
WITH ranges AS (
    SELECT i.*, n.manufacturer_key
    FROM source.incident i
    JOIN inference.incident_norm n USING (report_no)
    WHERE product_code IN ('278', '279', '280', '281')
      AND publication_date <= DATE '2026-11-04'
), matches AS (
    SELECT * FROM ranges
    WHERE incident_description ILIKE '%knob%'
      AND incident_description ~* '\m(bump|brush|lean|accidental|inadvertent|unintentional)\w*'
      AND incident_description ~* '\m(turn(s|ed|ing)? on|ignit\w*)\M'
), timed AS (
    SELECT *, lag(report_no) OVER w AS prior_report,
           lag(publication_date) OVER w AS prior_date,
           lag(publication_date, 2) OVER w AS second_prior_date
    FROM matches
    WINDOW w AS (PARTITION BY manufacturer_key, product_code ORDER BY publication_date, report_no)
)
SELECT manufacturer_key, product_code, prior_report, report_no, publication_date,
       (SELECT count(*) FROM ranges) AS reports_scanned,
       (SELECT count(*) FROM matches) AS narrative_matches
FROM timed
WHERE publication_date - prior_date <= 364
  AND (second_prior_date IS NULL OR publication_date - second_prior_date > 364)
ORDER BY publication_date, report_no;
```
