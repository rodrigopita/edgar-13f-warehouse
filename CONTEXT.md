# EDGAR 13F Warehouse

The language of a warehouse that resolves SEC Form 13F filings into the holdings each filer actually reported for each quarter. The terms below are used in model names, test names, docs and conversation; where the SEC and the data sets use another word, it is listed under _Avoid_ so the mapping is explicit.

## Filers and filings

**Filer**:
An institutional investment manager that files Form 13F, identified by its CIK.
_Avoid_: manager (reserved for other manager), institution, company, reporter

**Other manager**:
A manager named on a filing's cover page whose holdings the filing includes, or who reports some of the filer's holdings in a filing of its own.
_Avoid_: sub-manager, submanager, included manager

**Filing**:
One EDGAR submission by a filer, identified by its accession number. A filing is a holdings report, a notice, or an amendment to one of them.
_Avoid_: submission, document, form, record

**Period**:
The calendar quarter end a filing reports on, as EDGAR records it with the submission. The cover page repeats it, and in a few filings gets it wrong. One period collects filings across many filing dates and data sets.
_Avoid_: quarter, report date, as-of date, period of report

**Holdings report**:
A filing that lists the filer's holdings for a period, whether it lists all of them or combines its own list with holdings other managers report. EDGAR type 13F-HR.
_Avoid_: 13F, report, combination report

**Notice**:
A filing that says another manager reports all of the filer's holdings for a period. A notice carries no holdings. EDGAR type 13F-NT.
_Avoid_: NT, notice filing, notice report

**Holding**:
One entry of a holdings report's information table: a security, its class, the amount held, its value, the discretion it is held under and the voting authority over it. The same security can appear in several holdings of one filing, one per discretion or other manager; together they make a position.
_Avoid_: line, row, info table entry

**Security**:
What a holding is of, identified by CUSIP, and by FIGI as well in filings from 2023.
_Avoid_: issuer, instrument, asset, ticker

**Value unit**:
Whether a filing states market value in dollars or in thousands of dollars. The SEC moved filers to dollars on 2023-01-03, and not every filer followed.
_Avoid_: scale, denomination, units

## Amendments

**Original**:
The first holdings report a filer files for a period.
_Avoid_: initial filing, base filing, first filing

**Amendment**:
A filing that changes what an earlier filing says for the same filer and period, numbered by the filer. EDGAR types 13F-HR/A and 13F-NT/A.
_Avoid_: correction, /A, revised filing

**Restatement**:
An amendment that resubmits the entire holdings list as corrected. It stands in for every list filed before it for the period. The SEC's own term.
_Avoid_: full amendment, replacement, resubmission

**Addition**:
An amendment that lists only holdings being added and supplements the lists filed before it instead of replacing them. The cover page calls it adding new holdings entries, and the data sets record it as NEW HOLDINGS. Filers also resubmit whole lists under it, which coverage tells apart.
_Avoid_: new holdings amendment, supplement, partial amendment

**Confidential-treatment release**:
An addition a filer must make within six business days of the SEC denying, or ending, confidential treatment of holdings withheld from the original. The usual reason a hedge fund files many additions for one period.
_Avoid_: CT amendment, disclosure amendment

**Untyped amendment**:
An amendment whose cover page names neither restatement nor addition. Fifty-five exist in the data sets.
_Avoid_: unknown amendment, blank amendment

## Canonical state

**Lineage**:
The ordered chain of filings by one filer for one period: the original, then each amendment in filing order.
_Avoid_: history, version chain, filing sequence

**Filing order**:
The order in which a lineage's filings take effect: by filing date; within a date by the cover's amendment number, an original first; then by accession number.
_Avoid_: submission order, amendment order

**Supersedence**:
The relation by which a later filing in a lineage puts an earlier filing's holdings out of effect. A restatement supersedes every holdings report before it; an addition supersedes nothing.
_Avoid_: override, replacement, invalidation

**Superseded filing**:
A holdings report whose holdings are out of effect because a restatement follows it in the lineage.
_Avoid_: old filing, stale filing, replaced filing

**Effective filing**:
The latest original or restatement of a lineage. It and every addition filed after it are the contributing filings.
_Avoid_: standing filing, current restatement

**Contributing filing**:
A filing in a lineage whose holdings are in effect: the latest restatement, or the original when none exists, and every addition filed after it.
_Avoid_: active filing, live filing

**Coverage**:
The share of the securities of the filing an addition amends that the addition lists again. An addition with a coverage of nine tenths or more resubmits the list and is read as a restatement.
_Avoid_: overlap, repeat rate

**Copied holding**:
A holding of an addition identical to one already in effect for the same filer and period, in security, put or call, amount and its type, discretion and other managers. It is listed twice and held once, so it counts once.
_Avoid_: duplicate, repeated holding

**Canonical holdings**:
The holdings of a filer for a period with every amendment applied: the holdings of the contributing filings, nothing else. The warehouse's answer to what the filer reported.
_Avoid_: final holdings, resolved holdings, current holdings, latest holdings

**Data-quality row**:
A recorded fact about a filing or lineage that the rules could not settle or that the source contradicts, such as a holdings total that does not match the summary, an untyped amendment, or an amendment without an original. It travels with the data instead of stopping the build.
_Avoid_: error, exception, warning, anomaly

## Positions

**Position**:
A filer's canonical holdings of one security in one period, taken together whatever discretion or other manager each is held under. A put or a call on a security is a position of its own, apart from the security.
_Avoid_: stake, line, holding

**Previous period**:
The period three months before another. A filer's positions are compared with the previous period's only when the filer has canonical holdings in both; a period after a notice, a skipped period or a filer's first report has no entries or exits.
_Avoid_: last quarter, prior quarter, QoQ

**Entry**:
A position a filer has in a period and did not have in the previous period.
_Avoid_: new position, buy, opening

**Exit**:
A position a filer had in the previous period and does not have in this one.
_Avoid_: sale, sell-off, closing

**Increase**:
A position held in both periods whose share or principal amount, stated the same way in both, grew. The amount is the measure and not the value, which moves with price. A 13F lists holdings, not trades, so an increase may net several trades or be a stock split.
_Avoid_: buy, purchase, accumulation

**Decrease**:
A position held in both periods whose share or principal amount, stated the same way in both, shrank. Read like an increase.
_Avoid_: sell, sale, trim

**Weight**:
A position's share of its filer's value in a period, options left out.
_Avoid_: allocation, percentage, portfolio share

**Concentration**:
How much of a filer's value in a period sits in few positions: the share of its ten largest, and the sum of every position's squared weight.
_Avoid_: diversification, focus

**Overlap**:
How much two filers' portfolios have in common in a period: over the securities both hold, the smaller of their two weights, summed. One for identical portfolios, zero for disjoint ones.
_Avoid_: similarity, correlation, common holdings

## Sources

**Data set**:
One of the SEC's quarterly Form 13F data set zips, holding the filings submitted in its filing-date window. Fifty-four exist, from April 2013 to August 2026.
_Avoid_: dataset, bulk file, TSV, quarter file

**Walk**:
One pass of the daily index that discovers, lands and parses the filings of one day. The source of every filing after the last data set.
_Avoid_: crawl, scrape, incremental load

**Audit record**:
What one attempt of a walk or backfill run wrote about itself: what it discovered, landed, parsed or loaded, and what failed. Each attempt writes its own, so a rerun adds a record and the latest for a day stands.
_Avoid_: log, run log, manifest, report
