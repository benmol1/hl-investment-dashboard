select
    da.account_name                as account_id,
    dd.date                        as valuation_date,
    round(sum(fdh.value_gbp), 2)   as portfolio_value_gbp

from {{ ref('fct_daily_holdings') }} fdh
inner join {{ ref('dim_account') }} da on da.account_key = fdh.account_key
inner join {{ ref('dim_date') }}    dd on dd.date_key    = fdh.date_key

group by da.account_name, dd.date
having portfolio_value_gbp > 0
