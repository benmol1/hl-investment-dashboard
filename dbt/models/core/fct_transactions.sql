select
    t.transaction_id,
    da.account_key,
    df.fund_key,
    t.account_id,
    t.fund_id,
    df.fund_name,
    t.trade_date,
    t.settle_date,
    t.reference,
    t.raw_description,
    t.transaction_type,
    t.transaction_subtype,
    t.unit_cost_pence,
    t.quantity,
    t.value_gbp,
    t.is_trade,
    t.is_contribution

from {{ ref('base__hl_transactions') }} t
left join {{ ref('dim_account') }} da on da.account_name = t.account_id
left join {{ ref('dim_fund') }}    df on df.fund_id    = t.fund_id
