-- One row per security: a CUSIP that any canonical holding carries, with
-- a name, a class and a FIGI chosen from what filers reported, how many
-- FIGIs they reported, and whether the CUSIP is well formed and passes its
-- check digit. Canonical holdings only, so a security that appears only in
-- a superseded filing is not here, and a marts model that joins holdings
-- to this one loses nothing.
--
-- Filers spell one security many ways: on 2026-10-19, 66,197 of the
-- 150,725 CUSIPs in the canonical holdings carried more than one name.
-- The name and the class are each the most frequent among the CUSIP's
-- holdings in its last period, since the latest period carries a renamed
-- security's current name; a tie goes to the alphabetically first, so a
-- rebuild picks the same one. The FIGI stands only where the filers
-- reported exactly one for the CUSIP: 9,879 of the 24,067 CUSIPs with a
-- FIGI carried several, and 6,486 FIGIs named more than one CUSIP, so
-- the most frequent FIGI would be a guess. figi_count shows how many
-- were reported. A null never stands: nulls are left out of each
-- choice, and a CUSIP with only nulls has a null.
--
-- The check digit is the standard one: values 0 to 9 for digits, 10 to 35
-- for A to Z, 36, 37 and 38 for * @ #; every second value doubled, the
-- digits of each result summed, and the check is what brings the total to
-- a multiple of ten. The result is null for a CUSIP that is not well
-- formed, since a rule cannot say a string that is not a CUSIP fails it.
-- Some holdings carry no such CUSIP: on 2026-10-19, 21,222 CUSIPs behind
-- 193,191 holdings were not nine well-formed characters, 7,193 of them
-- eight. The placeholder 000000000, behind 6,359 holdings, is well
-- formed and passes its check digit, so neither column catches it. The
-- data are kept as filed, so both columns are facts about the row and
-- no filter.
-- The macros are in macros/cusip.sql and use ascii() and substr(), the
-- classification a pattern would do, which DuckDB and Snowflake spell
-- differently.

with cusip_summary as (
    select
        cusip,
        min(period_of_report) as first_period,
        max(period_of_report) as last_period,
        case when count(distinct figi) = 1 then min(figi) end as figi,
        count(distinct figi) as figi_count
    from {{ ref('canonical_holdings') }}
    group by cusip
),

last_period_holdings as (
    select
        holdings.cusip,
        holdings.name_of_issuer,
        holdings.title_of_class
    from {{ ref('canonical_holdings') }} as holdings
    inner join cusip_summary
        on cusip_summary.cusip = holdings.cusip
        and cusip_summary.last_period = holdings.period_of_report
),

name_choice as (
    select
        cusip,
        name_of_issuer
    from last_period_holdings
    where name_of_issuer is not null
    group by cusip, name_of_issuer
    qualify row_number() over (
        partition by cusip
        order by count(*) desc, name_of_issuer
    ) = 1
),

title_of_class_choice as (
    select
        cusip,
        title_of_class
    from last_period_holdings
    where title_of_class is not null
    group by cusip, title_of_class
    qualify row_number() over (
        partition by cusip
        order by count(*) desc, title_of_class
    ) = 1
),

cusip_forms as (
    select
        cusip,
        {{ cusip_is_well_formed('cusip') }} as is_well_formed,
        {% for character_index in range(1, 9) -%}
        {{ cusip_character_value('cusip', character_index) }} as value_{{ character_index }},
        {% endfor -%}
        ascii(substr(cusip, 9, 1)) - 48 as stated_check_digit
    from cusip_summary
),

cusip_checks as (
    select
        cusip,
        is_well_formed,
        case
            when is_well_formed then
                mod(10 - mod(
                    {{ cusip_digit_sum('value_1', 1) }}
                    + {{ cusip_digit_sum('value_2', 2) }}
                    + {{ cusip_digit_sum('value_3', 1) }}
                    + {{ cusip_digit_sum('value_4', 2) }}
                    + {{ cusip_digit_sum('value_5', 1) }}
                    + {{ cusip_digit_sum('value_6', 2) }}
                    + {{ cusip_digit_sum('value_7', 1) }}
                    + {{ cusip_digit_sum('value_8', 2) }},
                    10
                ), 10) = stated_check_digit
        end as has_valid_check_digit
    from cusip_forms
)

select
    cusip_summary.cusip,
    name_choice.name_of_issuer,
    title_of_class_choice.title_of_class,
    cusip_summary.figi,
    cusip_summary.figi_count,
    cusip_checks.is_well_formed,
    cusip_checks.has_valid_check_digit,
    cusip_summary.first_period,
    cusip_summary.last_period
from cusip_summary
inner join cusip_checks
    on cusip_checks.cusip = cusip_summary.cusip
left join name_choice
    on name_choice.cusip = cusip_summary.cusip
left join title_of_class_choice
    on title_of_class_choice.cusip = cusip_summary.cusip
