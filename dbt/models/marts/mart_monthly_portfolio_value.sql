with month_end_dates as (
    select
        account_id,
        dd.year_month,
        max(pv.date) as month_end_date
    from {{ ref('mart_portfolio_contributions') }} pv
    inner join {{ ref('dim_date') }} dd on dd.date = pv.date
    group by account_id, dd.year_month
),

monthly_contributions as (
    select
        dc.account_id,
        dd.year_month,
        sum(dc.contributed_today) as month_total_contributions_gbp
    from {{ ref('int_daily_contributions') }} dc
    inner join {{ ref('dim_date') }} dd on dd.date = dc.contribution_date
    group by dc.account_id, dd.year_month
)

select
    ams.account_id,
    ams.year_month,
    ams.financial_year,
    med.month_end_date,
    pv.portfolio_value_gbp as month_end_value_gbp,
    pv.cumulative_contributions_gbp,
    coalesce(mc.month_total_contributions_gbp,0) as month_total_contributions_gbp

from {{ ref('int_account_month_spine') }} ams
left join month_end_dates med
    on  med.account_id = ams.account_id
    and med.year_month = ams.year_month
left join {{ ref('mart_portfolio_contributions') }} pv
    on  pv.account_id = med.account_id
    and pv.date       = med.month_end_date
left join monthly_contributions mc
    on  mc.account_id = ams.account_id
    and mc.year_month = ams.year_month
