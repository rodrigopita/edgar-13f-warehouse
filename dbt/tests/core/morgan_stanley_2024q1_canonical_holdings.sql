-- Morgan Stanley, CIK 0000895421, period 2024-03-31: two NEW HOLDINGS
-- amendments, 0000895421-24-000436 and -000486, each resubmit all of the
-- original's holdings and say the firm is restating its 13F. Each repeats
-- every security of the filing it amends, so each reads as a restatement,
-- the second is the effective filing, and canonical holdings are its 46944
-- holdings alone. Expected rows and dollars come from the filings on
-- sec.gov, fetched 2026-10-20, and a separate Python pass over the 54
-- zips the same day finds the same filings, rows, units and dollars.
with expected as (
    select '0000895421-24-000486' as accession_number, 46944 as holdings, 1246388545549 as value_usd
),

actual as (
    select accession_number, count(*) as holdings, sum(value_usd) as value_usd
    from {{ ref('canonical_holdings') }}
    where cik = '0000895421' and period_of_report = '2024-03-31'::date
    group by accession_number
)

(select 'missing' as side, * from expected minus select 'missing', * from actual)
union all
(select 'unexpected' as side, * from actual minus select 'unexpected', * from expected)
