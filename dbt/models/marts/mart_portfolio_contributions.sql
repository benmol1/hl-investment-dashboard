with daily_contributions as (
    select
        da.account_name,
        dd.date               as contribution_date,
        sum(ft.value_gbp)     as contributed_today
    from {{ ref('fct_transactions') }}      ft
    inner join {{ ref('dim_transaction_type') }} dtt on dtt.transaction_type_key = ft.transaction_type_key
    inner join {{ ref('dim_account') }}          da  on da.account_key           = ft.account_key
    inner join {{ ref('dim_date') }}             dd  on dd.date_key              = ft.trade_date_key
    where dtt.contribution_indicator = 'Contribution'
    group by da.account_name, dd.date
),

cumulative_contribs as (
    select
        account_name,
        contribution_date,
        contributed_today,
        sum(contributed_today) over (
            partition by account_name
            order by contribution_date
            rows between unbounded preceding and current row
        ) as cumulative_contributions_gbp
    from daily_contributions
)

select
    pv.account_name,
    pv.valuation_date,
    pv.portfolio_value_gbp,
    coalesce(dc.contributed_today, 0)            as contributions_gbp,
    coalesce(cc.cumulative_contributions_gbp, 0) as cumulative_contributions_gbp

from {{ ref('mart_daily_portfolio_value') }} pv
left join daily_contributions dc
    on  dc.account_name      = pv.account_name
    and dc.contribution_date = pv.valuation_date
asof left join cumulative_contribs cc
    on  pv.account_name         = cc.account_name
    and pv.valuation_date     >= cc.contribution_date
