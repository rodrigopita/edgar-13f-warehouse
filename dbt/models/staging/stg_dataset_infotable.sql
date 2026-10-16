-- One row per holding in the data sets. The value is put in dollars by the
-- filing date of the holding's filing, which is why the submission is
-- joined here: the unit is a property of when the filing was made.
select
    holdings.accession_number,
    {{ dataset_number('holdings.infotable_sk') }} as infotable_sk,
    {{ dataset_text('holdings.nameofissuer') }} as name_of_issuer,
    {{ dataset_text('holdings.titleofclass') }} as title_of_class,
    upper({{ dataset_text('holdings.cusip') }}) as cusip,
    upper({{ dataset_text('holdings.figi') }}) as figi,
    {{ dataset_usd('holdings.value', 'submissions.filing_date') }} as value_usd,
    {{ dataset_number('holdings.sshprnamt') }} as shares_or_principal_amount,
    {{ dataset_text('holdings.sshprnamttype') }} as shares_or_principal_amount_type,
    {{ dataset_text('holdings.putcall') }} as put_call,
    {{ dataset_text('holdings.investmentdiscretion') }} as investment_discretion,
    {{ dataset_text('holdings.othermanager') }} as other_manager,
    {{ sequence_numbers('holdings.othermanager') }} as other_manager_sequence_numbers,
    {{ dataset_number('holdings.voting_auth_sole') }} as voting_sole,
    {{ dataset_number('holdings.voting_auth_shared') }} as voting_shared,
    {{ dataset_number('holdings.voting_auth_none') }} as voting_none,
    holdings.source_file,
    holdings.source_row,
    holdings.source_content_key,
    holdings.source_last_modified
from {{ source('raw', 'dataset_infotable') }} as holdings
left join {{ ref('stg_dataset_submission') }} as submissions
    on submissions.accession_number = holdings.accession_number
