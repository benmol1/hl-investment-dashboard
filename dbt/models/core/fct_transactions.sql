select
    -- Foreign keys
    da.account_key,
    df.fund_key,
    dtt.transaction_type_key,

    -- Date foreign keys
    tdd.date_key as trade_date_key,
    sdd.date_key as settle_date_key,

    -- Degenerate attributes
    t.transaction_id,
    t.reference as transaction_reference,
    t.raw_description,

    -- Numeric facts
    t.quantity,
    t.value_gbp

from {{ ref('base__hl_transactions') }} t
inner join {{ ref('dim_date') }}             tdd on tdd.date               = t.trade_date
left join  {{ ref('dim_date') }}             sdd on sdd.date               = t.settle_date
left join  {{ ref('dim_account') }}          da  on da.account_name        = t.account_id
left join  {{ ref('dim_fund') }}             df  on df.fund_id             = t.fund_id
left join  {{ ref('dim_transaction_type') }} dtt on dtt.transaction_type   = t.transaction_type
                                                and dtt.transaction_subtype is not distinct from t.transaction_subtype