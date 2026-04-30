with buys as (
    select
        account_id,
        fund_id,
        sum(abs(value_gbp)) as total_buy_cost,
        sum(quantity)       as total_units_bought
    from {{ ref('stg_transactions') }}
    where transaction_type in ('BUY', 'SWITCH_IN')
      and fund_id  is not null
      and quantity is not null
    group by account_id, fund_id
),

sells as (
    select
        account_id,
        fund_id,
        sum(abs(value_gbp)) as total_sell_proceeds,
        sum(quantity)       as total_units_sold
    from {{ ref('stg_transactions') }}
    where transaction_type in ('SELL', 'SWITCH_OUT')
      and fund_id  is not null
      and quantity is not null
    group by account_id, fund_id
)

select
    b.account_id,
    b.fund_id,
    b.total_buy_cost,
    b.total_units_bought,
    coalesce(s.total_sell_proceeds, 0) as total_sell_proceeds,
    coalesce(s.total_units_sold, 0)    as total_units_sold,

    -- Simplified cost basis: total purchase cost minus sale proceeds.
    -- Does not use FIFO or weighted average; switching events are excluded.
    -- See README known caveats — suitable as a guide, not a tax record.
    greatest(b.total_buy_cost - coalesce(s.total_sell_proceeds, 0), 0) as cost_basis_gbp

from buys b
left join sells s
    on s.account_id = b.account_id
    and s.fund_id  = b.fund_id
