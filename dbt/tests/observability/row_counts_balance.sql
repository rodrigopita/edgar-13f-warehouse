-- Every raw holding row reaches holdings, every holding is in a superseded
-- or a contributing filing, and canonical holdings are never more than the
-- contributing ones.
select *
from {{ ref('row_counts') }}
where raw_rows <> holdings
    or unresolved_holdings <> 0
    or copied_holdings < 0
