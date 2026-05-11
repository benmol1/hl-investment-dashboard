select
    date_key,
    account_key,
    fund_key,
    'Fund'         as holding_type,
    units_held,
    fund_price_gbp,
    value_gbp
from {{ ref('int_daily_fund_values') }}

union all

select
    date_key,
    account_key,
    null           as fund_key,
    'Cash'         as holding_type,
    null           as units_held,
    null           as fund_price_gbp,
    value_gbp
from {{ ref('int_daily_cash_values') }}
