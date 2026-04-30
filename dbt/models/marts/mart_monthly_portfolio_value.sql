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
        pv.account_id,
        dd.year_month,
        sum(pv.contributions_gbp) as monthly_contributions_gbp
    from {{ ref('mart_portfolio_contributions') }} pv
    inner join {{ ref('dim_date') }} dd on dd.date = pv.date
    group by pv.account_id, dd.year_month
)

select
    med.account_id,
    med.year_month,
    dd.financial_year,
    med.month_end_date,
    pv.portfolio_value_gbp,
    pv.cumulative_contributions_gbp,
    mc.monthly_contributions_gbp

from month_end_dates med
inner join {{ ref('dim_date') }} dd
    on dd.date = med.month_end_date
inner join {{ ref('mart_portfolio_contributions') }} pv
    on  pv.account_id = med.account_id
    and pv.date       = med.month_end_date
inner join monthly_contributions mc
    on  mc.account_id  = med.account_id
    and mc.year_month  = med.year_month
