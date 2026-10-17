-- Reconciliation between raw and core: every raw holding row reaches the
-- holdings model once, on each path. The walk counts one file version per
-- filing, the one staging keeps.
with counts as (
    select
        'data_set' as origin,
        (select count(*) from {{ source('raw', 'dataset_infotable') }}) as raw_rows,
        (select count(*) from {{ ref('holdings') }} where origin = 'data_set') as core_rows
    union all
    select
        'walk',
        (select count(*) from {{ ref('stg_xml_filing_records') }} where record_type = 'holding'),
        (select count(*) from {{ ref('holdings') }} where origin = 'walk')
)

select * from counts where raw_rows <> core_rows
