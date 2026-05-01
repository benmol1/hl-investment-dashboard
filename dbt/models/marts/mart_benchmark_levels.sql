select
    index_id,
    market_date,
    index_level,
    ticker

from {{ ref('stg_benchmarks') }}
