-- How much of the filing it amends each addition repeats. One row per
-- filing whose role as typed is addition; the terms are those of
-- CONTEXT.md and the rules those of docs/scope.md, Decisions, 2026-10-15
-- to 2026-10-17.
--
-- An addition is meant to list only holdings being added, but filers also
-- resubmit the whole list under that type: 1,040 of the 5,121 additions in
-- the data sets repeat 90 percent or more of the securities of the filing
-- they amend, and counted as additions they sum with the list they repeat.
-- The compared filing is the latest filing before the addition in filing
-- order whose role as typed is original or restatement. Typed matters:
-- comparing with the role after this model would make an addition depend
-- on itself, and it lets a second resubmitted addition compare with the
-- original, as the first does.
--
-- Coverage is the distinct securities of the addition also in the compared
-- filing, over the distinct securities of the compared filing. It is null
-- when there is no compared filing or it has no holdings, and the addition
-- then stays an addition. At 0.9 or more the addition is read as a
-- restatement; lineage_filings turns that into its role. The threshold is
-- tested on whole numbers so that exactly 0.9 never depends on how a
-- division rounds.
--
-- The typed role comes from the macro lineage_filings uses, so the two
-- cannot drift apart. Holdings has 124 million rows, so only the holdings
-- of additions and of their compared filings are aggregated.

with ordered as (
    select
        accession_number,
        cik,
        period_of_report,
        submission_type,
        amendment_type,
        row_number() over (
            partition by cik, period_of_report
            order by {{ filing_order() }}
        ) as filing_position
    from {{ ref('filings') }}
),

typed as (
    select
        *,
        {{ typed_filing_role() }} as typed_role
    from ordered
),

additions as (
    select accession_number, cik, period_of_report, filing_position
    from typed
    where typed_role = 'addition'
),

compared as (
    select
        additions.accession_number,
        additions.cik,
        additions.period_of_report,
        earlier.accession_number as compared_accession_number
    from additions
    left join typed as earlier
        on earlier.cik = additions.cik
        and earlier.period_of_report = additions.period_of_report
        and earlier.typed_role in ('original', 'restatement')
        and earlier.filing_position < additions.filing_position
    qualify row_number() over (
        partition by additions.accession_number
        order by earlier.filing_position desc
    ) = 1
),

compared_filings as (
    select accession_number from compared
    union
    select compared_accession_number from compared where compared_accession_number is not null
),

filing_securities as (
    select distinct holdings.accession_number, holdings.cusip
    from {{ ref('holdings') }} as holdings
    inner join compared_filings
        on compared_filings.accession_number = holdings.accession_number
    where holdings.cusip is not null
),

compared_counts as (
    select accession_number, count(*) as security_count
    from filing_securities
    group by accession_number
),

repeated_counts as (
    select compared.accession_number, count(*) as security_count
    from compared
    inner join filing_securities as added
        on added.accession_number = compared.accession_number
    inner join filing_securities as in_compared
        on in_compared.accession_number = compared.compared_accession_number
        and in_compared.cusip = added.cusip
    group by compared.accession_number
),

counted as (
    select
        compared.accession_number,
        compared.cik,
        compared.period_of_report,
        compared.compared_accession_number,
        case
            when compared.compared_accession_number is not null
                then coalesce(compared_counts.security_count, 0)
        end as compared_securities,
        case
            when compared.compared_accession_number is not null
                then coalesce(repeated_counts.security_count, 0)
        end as repeated_securities
    from compared
    left join compared_counts
        on compared_counts.accession_number = compared.compared_accession_number
    left join repeated_counts
        on repeated_counts.accession_number = compared.accession_number
)

select
    accession_number,
    cik,
    period_of_report,
    compared_accession_number,
    compared_securities,
    repeated_securities,
    repeated_securities / nullif(compared_securities, 0) as coverage,
    coalesce(compared_securities > 0 and repeated_securities * 10 >= compared_securities * 9, false)
        as is_read_as_restatement
from counted
