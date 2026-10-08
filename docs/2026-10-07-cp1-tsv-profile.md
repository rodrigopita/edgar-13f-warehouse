# cp1: profile of the SEC 13F data sets

Written 2026-10-07 from `uv run --env-file .env python -m include.sec_cli profile`, one streaming pass over the 54 zips downloaded on 2026-10-06 (3.05 GB). The per-data-set JSON lives under `data/profile/`, which is gitignored; this document is the record the cp1 done-criterion asks for.

## What the numbers say

- **54 data sets tile the timeline without a gap**, from 2013q2 to 01jun2026-31aug2026. The first 43 are named by calendar quarter, the rest by filing-date window; the newest ends 2026-08-31, the day before the XML walk begins.
- **409,685 filings and 124,012,468 holdings rows.** INFOTABLE grew from 87,715 rows in 2013q2 to 3,830,274 in the newest window; filings per window from 166 to 11,852.
- **The VALUE unit change is visible in the data, not only in the readme.** The share of rows with VALUE under 1,000 sits between 47% and 63% through 2022q4 and falls to 16% in 2023q1; the median VALUE jumps from 534 to 235,513, a factor of 440. Values before 2023-01-03 are in thousands of dollars and must be multiplied by 1,000 in the core layer; the XML path, which starts in 2026, needs no conversion.
- **FIGI is empty before 2023** and filled on 7% to 12% of rows after, so CUSIP is the only identifier for the history and FIGI-based enrichment can only ever cover the recent tail.
- **Amendments are 16,483 of 409,685 filings (4%)**: 15,727 holdings-report amendments and 756 notice amendments. 16,469 carry an AMENDMENTTYPE, 11,140 RESTATEMENT and 5,329 NEW HOLDINGS, and 14 carry none. The two values are exactly those the XML parser types as a Literal.
- **One zip, 01jun2025-31aug2025, packs its tables inside a folder**; the other 53 are flat. The profiler matches members by base name.

## Per data set

| data set            | window                   | zip MB | filings | holdings rows |          value sum | under 1,000 |  FIGI |
| ------------------- | ------------------------ | -----: | ------: | ------------: | -----------------: | ----------: | ----: |
| 2013q2              | 2013-04-01 to 2013-06-30 |      2 |     166 |        87,715 |      2,338,624,275 |       46.8% |  0.0% |
| 2013q3              | 2013-07-01 to 2013-09-30 |     36 |   5,227 |     1,533,636 |    514,959,065,096 |       53.9% |  0.0% |
| 2013q4              | 2013-10-01 to 2013-12-31 |     36 |   5,043 |     1,519,317 |  3,827,742,094,892 |       53.5% |  0.0% |
| 2014q1              | 2014-01-01 to 2014-03-31 |     38 |   5,425 |     1,584,857 |    536,185,067,507 |       53.6% |  0.0% |
| 2014q2              | 2014-04-01 to 2014-06-30 |     38 |   5,415 |     1,588,232 |    672,939,968,225 |       52.8% |  0.0% |
| 2014q3              | 2014-07-01 to 2014-09-30 |     40 |   5,482 |     1,638,747 |    504,894,656,491 |       52.9% |  0.0% |
| 2014q4              | 2014-10-01 to 2014-12-31 |     39 |   5,465 |     1,636,491 |    328,727,642,739 |       53.8% |  0.0% |
| 2015q1              | 2015-01-01 to 2015-03-31 |     42 |   6,045 |     1,768,828 |    509,801,752,579 |       55.3% |  0.0% |
| 2015q2              | 2015-04-01 to 2015-06-30 |     41 |   5,914 |     1,711,601 |    481,626,283,079 |       53.8% |  0.0% |
| 2015q3              | 2015-07-01 to 2015-09-30 |     43 |   6,000 |     1,772,870 |    407,511,209,766 |       53.9% |  0.0% |
| 2015q4              | 2015-10-01 to 2015-12-31 |     41 |   5,975 |     1,695,347 |    160,326,170,518 |       55.5% |  0.0% |
| 2016q1              | 2016-01-01 to 2016-03-31 |     42 |   6,072 |     1,710,477 |    198,617,062,022 |       55.6% |  0.0% |
| 2016q2              | 2016-04-01 to 2016-06-30 |     42 |   6,034 |     1,747,959 |    191,974,165,827 |       56.7% |  0.0% |
| 2016q3              | 2016-07-01 to 2016-09-30 |     42 |   6,007 |     1,742,410 |    175,093,736,486 |       56.5% |  0.0% |
| 2016q4              | 2016-10-01 to 2016-12-31 |     42 |   5,994 |     1,716,138 |    186,462,705,448 |       56.0% |  0.0% |
| 2017q1              | 2017-01-01 to 2017-03-31 |     44 |   6,210 |     1,805,106 |    117,464,634,132 |       55.4% |  0.0% |
| 2017q2              | 2017-04-01 to 2017-06-30 |     43 |   6,218 |     1,790,999 |    259,254,286,631 |       55.0% |  0.0% |
| 2017q3              | 2017-07-01 to 2017-09-30 |     43 |   6,207 |     1,746,541 |    261,867,913,391 |       54.5% |  0.0% |
| 2017q4              | 2017-10-01 to 2017-12-31 |     43 |   6,174 |     1,801,866 |    251,260,374,358 |       56.0% |  0.0% |
| 2018q1              | 2018-01-01 to 2018-03-31 |     45 |   6,570 |     1,879,731 |    341,962,393,223 |       55.4% |  0.0% |
| 2018q2              | 2018-04-01 to 2018-06-30 |     46 |   6,622 |     1,925,787 |    294,067,214,189 |       56.5% |  0.0% |
| 2018q3              | 2018-07-01 to 2018-09-30 |     47 |   6,647 |     1,934,475 |    290,527,066,496 |       55.1% |  0.0% |
| 2018q4              | 2018-10-01 to 2018-12-31 |     48 |   6,659 |     2,040,197 |    728,233,050,348 |       56.4% |  0.0% |
| 2019q1              | 2019-01-01 to 2019-03-31 |     47 |   6,887 |     1,945,558 |    253,192,973,105 |       59.1% |  0.0% |
| 2019q2              | 2019-04-01 to 2019-06-30 |     54 |   7,144 |     2,301,992 |    295,002,574,569 |       58.6% |  0.0% |
| 2019q3              | 2019-07-01 to 2019-09-30 |     50 |   6,932 |     2,116,186 |    352,565,900,007 |       57.2% |  0.0% |
| 2019q4              | 2019-10-01 to 2019-12-31 |     50 |   6,981 |     2,116,307 |    318,169,730,536 |       57.9% |  0.0% |
| 2020q1              | 2020-01-01 to 2020-03-31 |     50 |   7,285 |     2,159,065 |    351,853,355,440 |       58.3% |  0.0% |
| 2020q2              | 2020-04-01 to 2020-06-30 |     50 |   7,296 |     2,163,834 |    286,600,210,090 |       62.9% |  0.0% |
| 2020q3              | 2020-07-01 to 2020-09-30 |     49 |   7,157 |     2,089,408 |    345,135,402,774 |       59.0% |  0.0% |
| 2020q4              | 2020-10-01 to 2020-12-31 |     50 |   7,237 |     2,156,794 |    378,131,069,905 |       58.3% |  0.0% |
| 2021q1              | 2021-01-01 to 2021-03-31 |     57 |   7,883 |     2,454,113 |    604,395,922,207 |       57.6% |  0.0% |
| 2021q2              | 2021-04-01 to 2021-06-30 |     56 |   7,927 |     2,376,681 |    466,701,723,520 |       56.1% |  0.0% |
| 2021q3              | 2021-07-01 to 2021-09-30 |     63 |   8,096 |     2,660,728 |    487,634,681,508 |       57.5% |  0.0% |
| 2021q4              | 2021-10-01 to 2021-12-31 |     61 |   7,985 |     2,569,324 |    553,888,537,516 |       56.7% |  0.0% |
| 2022q1              | 2022-01-01 to 2022-03-31 |     64 |   8,921 |     2,684,317 |    506,926,278,357 |       56.7% |  0.0% |
| 2022q2              | 2022-04-01 to 2022-06-30 |     63 |   8,906 |     2,603,731 |    478,021,596,393 |       58.0% |  0.0% |
| 2022q3              | 2022-07-01 to 2022-09-30 |     63 |   8,948 |     2,632,327 |    383,707,291,930 |       59.7% |  0.0% |
| 2022q4              | 2022-10-01 to 2022-12-31 |     63 |   9,010 |     2,622,058 |    439,604,139,306 |       59.5% |  0.0% |
| 2023q1              | 2023-01-01 to 2023-03-31 |     72 |   9,201 |     2,786,017 | 35,546,228,073,892 |       16.0% |  7.3% |
| 2023q2              | 2023-04-01 to 2023-06-30 |     69 |   9,113 |     2,672,308 | 44,596,652,787,378 |       13.2% |  7.6% |
| 2023q3              | 2023-07-01 to 2023-09-30 |     70 |   9,108 |     2,724,039 | 47,830,316,004,967 |       11.5% |  7.8% |
| 2023q4              | 2023-10-01 to 2023-12-31 |     73 |   9,196 |     2,886,468 | 47,402,889,117,519 |       11.7% |  7.2% |
| 01jan2024-29feb2024 | 2024-01-01 to 2024-02-29 |     73 |   9,433 |     2,848,736 | 46,457,711,530,559 |       10.4% |  8.4% |
| 01mar2024-31may2024 | 2024-03-01 to 2024-05-31 |     78 |   9,884 |     3,026,705 | 58,474,185,808,643 |        9.1% |  8.2% |
| 01jun2024-31aug2024 | 2024-06-01 to 2024-08-31 |     84 |  10,117 |     3,278,515 | 58,662,320,563,639 |        9.8% |  7.9% |
| 01sep2024-30nov2024 | 2024-09-01 to 2024-11-30 |     82 |   9,891 |     3,201,864 | 62,489,663,358,949 |        9.5% |  7.3% |
| 01dec2024-28feb2025 | 2024-12-01 to 2025-02-28 |     87 |  10,605 |     3,362,299 | 68,591,599,464,346 |        8.7% | 10.9% |
| 01mar2025-31may2025 | 2025-03-01 to 2025-05-31 |     88 |  10,765 |     3,440,002 | 62,010,350,252,183 |        9.4% | 10.7% |
| 01jun2025-31aug2025 | 2025-06-01 to 2025-08-31 |     86 |  10,799 |     3,360,306 | 63,404,539,376,904 |        9.2% | 11.0% |
| 01sep2025-30nov2025 | 2025-09-01 to 2025-11-30 |     86 |  10,422 |     3,267,091 | 70,168,009,002,201 |        7.2% | 11.5% |
| 01dec2025-28feb2026 | 2025-12-01 to 2026-02-28 |     90 |  11,372 |     3,473,209 | 71,071,665,530,490 |        7.4% | 11.7% |
| 01mar2026-31may2026 | 2026-03-01 to 2026-05-31 |     99 |  11,761 |     3,822,885 | 81,538,368,120,783 |        7.1% | 12.2% |
| 01jun2026-31aug2026 | 2026-06-01 to 2026-08-31 |    101 |  11,852 |     3,830,274 | 83,983,342,644,607 |        7.2% | 11.7% |

## Totals

| table         | rows across all data sets |
| ------------- | ------------------------: |
| SUBMISSION    |                   409,685 |
| COVERPAGE     |                   409,685 |
| INFOTABLE     |               124,012,468 |
| OTHERMANAGER  |                   207,051 |
| OTHERMANAGER2 |                   163,101 |
| SIGNATURE     |                   409,685 |
| SUMMARYPAGE   |                   326,126 |

| submission type | filings |
| --------------- | ------: |
| 13F-HR          | 307,228 |
| 13F-HR/A        |  15,727 |
| 13F-NT          |  85,974 |
| 13F-NT/A        |     756 |

| amendment type | filings |
| -------------- | ------: |
| NEW HOLDINGS   |   5,329 |
| RESTATEMENT    |  11,140 |

## The cp3 test filer

Candidates ranked by periods with two or more holdings-report amendments, keeping only filers whose largest table is between 50 and 3,000 rows so a period can be checked by hand against EDGAR.

| CIK        | periods with 2+ amendments | restatements | new holdings | both | largest table | periods |
| ---------- | -------------------------: | -----------: | -----------: | ---- | ------------: | ------: |
| 0001132716 |                         53 |           14 |          200 | yes  |           948 |      54 |
| 0001595082 |                         49 |            2 |          355 | yes  |           589 |      50 |
| 0001011443 |                         40 |            3 |          125 | yes  |         1,156 |      56 |
| 0001390113 |                         40 |            3 |          151 | yes  |           698 |      53 |
| 0001453072 |                         36 |            3 |          119 | yes  |           704 |      56 |
| 0001438284 |                         36 |            2 |          142 | yes  |         1,727 |      39 |
| 0001001085 |                         28 |           30 |           72 | yes  |           690 |      58 |
| 0000909661 |                         27 |            2 |          100 | yes  |           307 |      53 |
| 0001297376 |                         27 |           37 |           27 | yes  |         2,072 |      53 |
| 0001508097 |                         24 |           77 |            1 | yes  |            61 |      63 |

| CIK        | filer                                                               |
| ---------- | ------------------------------------------------------------------- |
| 0001132716 | O'Connor, a distinct business unit of UBS Asset Management Americas |
| 0001595082 | Davidson Kempner Capital Management LP                              |
| 0001011443 | HBK Investments L P                                                 |
| 0001390113 | Taconic Capital Advisors LP                                         |
| 0001453072 | Alyeska Investment Group, L.P.                                      |
| 0001438284 | Oxford Asset Management LLP                                         |
| 0001001085 | Brookfield Corp /ON/                                                |
| 0000909661 | Farallon Capital Management, L.L.C.                                 |
| 0001297376 | Advisors Asset Management, Inc.                                     |
| 0001508097 | Sanders Capital, LLC                                                |

Two patterns in the list. The hedge funds at the top file almost only NEW HOLDINGS amendments, many per period: positions held under confidential treatment are disclosed later as additions, which is the confidential-treatment mechanism rather than correction. Brookfield and Advisors Asset Management mix both types in comparable numbers, which is what the restatement-versus-addition logic has to get right in one filer.

**Chosen: Brookfield Corp /ON/, CIK 0001001085, period 2018-06-30.** Original of 191 holdings filed 2018-08-14; a RESTATEMENT filed 2018-11-14 holding two rows, Hawaiian Telcom Holdco and Cincinnati Bell, both under defined discretion for other manager 4; a RESTATEMENT of 191 rows the next day; a NEW HOLDINGS of one row on 2018-12-14. A restatement that formally replaces the report but carries one sub-manager's slice, corrected a day later, then an addition: the three cases the canonical state must resolve, in one period, checked against EDGAR on 2026-10-08 (accessions 0000950123-18-008668, -011987, -012060, -012410). Period 2017-12-31 is the second case. Advisors Asset Management, CIK 0001297376, is the tidy control: one addition and one full restatement per period.
