select
    account_id,
    fund_id,
    trade_date,
    sum(unit_delta) over (
        partition by account_id, fund_id
        order by trade_date
    ) as units_held

from {{ ref('int_trade_unit_deltas') }}

order by account_id, fund_id, trade_date
