{#-
  The lineage rules that more than one model applies, written once. The
  terms are those of CONTEXT.md and the rules those of docs/scope.md,
  Decisions, 2026-10-15 to 2026-10-17.
-#}

{#-
  Filing order within a lineage, as the body of an order by: filing date;
  within a date the cover's amendment number, an original first since it
  has none; then the accession number, whose last six digits count the
  submitter's filings.
-#}
{% macro filing_order() -%}
    filing_date, amendment_no nulls first, accession_number
{%- endmacro %}

{#-
  The role of a filing as typed, before any addition is read as a
  restatement: the submission type decides original, amendment or notice,
  the cover's amendment type decides restatement or addition. The first
  13F-HR of a lineage is the original and a later one counts as a
  restatement; an amendment with no type counts as a restatement. Reads
  the columns of a filing and its position in filing order, which the
  argument names, and must run in a select that has the whole lineage in
  view.
-#}
{% macro typed_filing_role(position='filing_position') -%}
    case
        when submission_type like '13F-NT%' then 'notice'
        when submission_type = '13F-HR' and {{ position }} = min(
            case when submission_type = '13F-HR' then {{ position }} end
        ) over (partition by cik, period_of_report) then 'original'
        when submission_type = '13F-HR' then 'restatement'
        when amendment_type = 'NEW HOLDINGS' then 'addition'
        else 'restatement'
    end
{%- endmacro %}

{#-
  True for a holding that an earlier filing of the same lineage already
  holds, identical in security, put or call, amount, amount type,
  discretion and other managers. The other managers are an array compared
  as filed, in order, as the text array_to_string makes of it. A window
  partitions nulls together, so the comparison is null-safe. The select
  must hold the contributing filings only and carry cik, period_of_report
  and filing_position. Holdings of one filing never match each other,
  since only a strictly earlier position counts.
-#}
{% macro is_copied_holding() -%}
    min(filing_position) over (
        partition by
            cik,
            period_of_report,
            cusip,
            put_call,
            shares_or_principal_amount,
            shares_or_principal_amount_type,
            investment_discretion,
            array_to_string(other_manager_sequence_numbers, ',')
    ) < filing_position
{%- endmacro %}
