select
    account_id,
    fund_id,
    trade_date,
    sum(quantity * unit_direction) as unit_delta

from {{ ref('base__hl_transactions') }}
where is_trade
  and fund_id is not null
  and quantity is not null

group by account_id, fund_id, trade_date
