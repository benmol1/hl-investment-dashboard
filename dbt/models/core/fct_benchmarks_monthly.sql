with daily_levels as (
    select
        p.index_id,
        p.ticker,
        dd.date_key,
        dd.year_month,
        p.index_level
    from {{ ref('base__hl_benchmarks') }} p
    inner join {{ ref('dim_date') }} dd on dd.date = p.market_date
),

-- Calendar month-end date key per year_month, used so benchmark dates align
-- with fund prices (which use dim_date.month_end_indicator = 'Month End').
calendar_month_ends as (
    select year_month, date_key as month_end_date_key
    from {{ ref('dim_date') }}
    where month_end_indicator = 'Month End'
)

select
    cme.month_end_date_key               as date_key,
    dl.index_id,
    dl.ticker,
    dl.year_month,
    last(dl.index_level order by dl.date_key) as month_end_level
from daily_levels dl
inner join calendar_month_ends cme on cme.year_month = dl.year_month
group by cme.month_end_date_key, dl.index_id, dl.ticker, dl.year_month
