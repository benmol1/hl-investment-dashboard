select
    index_id,
    date,
    level,
    ticker

from {{ source('hl_dashboard', 'benchmarks') }}
