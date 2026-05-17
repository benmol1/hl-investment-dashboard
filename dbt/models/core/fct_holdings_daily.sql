select
    date_key,
    account_key,
    fund_key,
    'Fund'         as holding_type,
    units_held,
    fund_price_gbp,
    value_gbp
from {{ ref('int_fund_values_daily') }}

union all

select
    date_key,
    account_key,
    null           as fund_key,
    'Cash'         as holding_type,
    null           as units_held,
    null           as fund_price_gbp,
    value_gbp
from {{ ref('int_cash_values_daily') }}
