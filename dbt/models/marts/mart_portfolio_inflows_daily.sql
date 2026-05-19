with
-- Inflow cash flows (contributions + transfers) aggregated by account and trade date.
daily_inflows as (
    select
        da.account_name,
        dd.date               as inflow_date,
        sum(ft.value_gbp)     as inflow_today
    from {{ ref('fct_transactions') }}      ft
    inner join {{ ref('dim_transaction_type') }} dtt on dtt.transaction_type_key = ft.transaction_type_key
    inner join {{ ref('dim_account') }}          da  on da.account_key           = ft.account_key
    inner join {{ ref('dim_date') }}             dd  on dd.date_key              = ft.trade_date_key
    where dtt.contribution_indicator in ('Contribution', 'Transfer')
    group by da.account_name, dd.date
),

-- Running total of inflows per account over time.
cumulative_inflows as (
    select
        account_name,
        inflow_date,
        inflow_today,
        sum(inflow_today) over (
            partition by account_name
            order by inflow_date
            rows between unbounded preceding and current row
        ) as cumulative_inflows_gbp
    from daily_inflows
)

select
    pv.account_name,
    pv.valuation_date,
    pv.portfolio_value_gbp,
    coalesce(di.inflow_today, 0)           as inflows_gbp,
    coalesce(ci.cumulative_inflows_gbp, 0) as cumulative_inflows_gbp

from {{ ref('mart_portfolio_value_daily') }} pv
left join daily_inflows di
    on  di.account_name = pv.account_name
    and di.inflow_date  = pv.valuation_date
asof left join cumulative_inflows ci
    on  pv.account_name       = ci.account_name
    and pv.valuation_date   >= ci.inflow_date
