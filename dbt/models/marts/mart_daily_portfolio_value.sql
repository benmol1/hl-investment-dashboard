select
    account_id,
    valuation_date,
    round(sum(value_gbp), 2) as portfolio_value_gbp

from {{ ref('int_daily_fund_values') }}

group by account_id, valuation_date
having portfolio_value_gbp > 0
