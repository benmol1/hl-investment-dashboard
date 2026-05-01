select
    index_id,
    date    as market_date,
    level   as index_level,
    ticker

from {{ source('hl_dashboard', 'benchmarks') }}
