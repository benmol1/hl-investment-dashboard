select
    id,
    account_id,
    fund_id,
    trade_date,
    settle_date,
    reference,
    raw_description,
    transaction_type,
    transaction_subtype,
    unit_cost_pence,
    quantity,
    value_gbp,

    -- Derived flags used by downstream intermediate models
    transaction_type in ('BUY', 'SELL', 'SWITCH_IN', 'SWITCH_OUT') as is_trade,
    transaction_type = 'CONTRIBUTION'                               as is_contribution,

    -- HL sign convention: value_gbp < 0 means money left the account (a purchase).
    -- Encoding this once here avoids repeating the CASE expression in every delta CTE.
    case when value_gbp < 0 then 1 else -1 end as unit_direction

from {{ source('hl_dashboard', 'transactions') }}
