with account_open_months as (
    select account_id, min(year_month) as open_year_month
    from (
        select account_id, dd.year_month
        from {{ ref('int_daily_contributions') }} dc
        inner join {{ ref('dim_date') }} dd on dd.date = dc.contribution_date
        union all
        select account_id, dd.year_month
        from {{ ref('mart_daily_portfolio_value') }} pv
        inner join {{ ref('dim_date') }} dd on dd.date = pv.valuation_date
    )
    group by account_id
)

select
    aom.account_id,
    dd.year_month,
    max(dd.financial_year) as financial_year
from account_open_months aom
inner join {{ ref('dim_date') }} dd
    on  dd.year_month >= aom.open_year_month
    and dd.date       <= current_date
group by aom.account_id, dd.year_month
