with daily_levels as (
    select
        p.index_id,
        p.ticker,
        dd.date_key,
        dd.year_month,
        p.index_level
    from {{ ref('base__hl_benchmarks') }} p
    inner join {{ ref('dim_date') }} dd on dd.date = p.market_date
)

select
    max(date_key)                        as date_key,
    index_id,
    ticker,
    year_month,
    last(index_level order by date_key)  as month_end_level
from daily_levels
group by index_id, ticker, year_month
