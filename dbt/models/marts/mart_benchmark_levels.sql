select
    index_id,
    date,
    level,
    ticker

from {{ ref('stg_benchmarks') }}
