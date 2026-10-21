-- The data-set path against the separate Python pass over the 54 zips of
-- 2026-10-20, which left 115,478,173 canonical holdings. The zips cannot
-- see the walk, so the data-set canonical holdings and those a walk
-- restatement set aside add up to that pass however many walk filings
-- have loaded since: 115,413,639 and 64,534 on 2026-10-20, 115,413,519 and
-- 64,654 on 2026-10-21. One event would move the sum and mean no error: a
-- walk restatement superseding a lineage whose data-set additions had
-- copied holdings, which the pass leaves out and set_aside_by_walk counts.
-- The data sets are fixed history until the next one is loaded, which
-- moves this number on purpose.
select origin, canonical_holdings, set_aside_by_walk,
       canonical_holdings + set_aside_by_walk as data_set_canonical_without_walk
from {{ ref('row_counts') }}
where origin = 'data_set'
    and canonical_holdings + set_aside_by_walk <> 115478173
