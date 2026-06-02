-- TODO: include cash holdings so this mart is consistent with other marts that show
-- both fund and cash positions. Currently filtered to holding_type = 'Fund' only.
-- Cash rows have no fund_key/fund_price/units, so they'll need separate handling
-- (e.g. a UNION with fct_cash_position_daily, or relaxing the holding_type filter
-- and coalescing the fund-specific columns to null/0 for cash rows).

with
-- Most recent date for which fund we have at least 1 fund holding.
latest_date_key as (
    select max(date_key) as date_key
    from {{ ref('fct_holdings_daily') }}
    where holding_type = 'Fund'
),

-- Fund positions on the latest date, excluding near-zero balances.
holdings_latest as (
    select
        fct_hd.account_key,
        fct_hd.fund_key,
        dd.date   as valuation_date,
        fct_hd.units_held,
        fct_hd.fund_price_gbp,
        fct_hd.value_gbp
    from {{ ref('fct_holdings_daily') }} fct_hd
    inner join latest_date_key ldk on ldk.date_key = fct_hd.date_key
    inner join {{ ref('dim_date') }}    dd  on dd.date_key    = fct_hd.date_key
    where fct_hd.holding_type = 'Fund'
      and fct_hd.units_held   >= 0.01
),

-- Total amount invested per (account, fund) across all BUY and SWITCH_IN trades.
buy_cost as (
    select
        ft.account_key,
        ft.fund_key,
        sum(abs(ft.value_gbp)) as total_cost_gbp
    from {{ ref('fct_transactions') }} ft
    inner join {{ ref('dim_transaction_type') }} dtt on dtt.transaction_type_key = ft.transaction_type_key
    where dtt.transaction_type in ('BUY', 'SWITCH_IN')
      and ft.fund_key is not null
      and ft.quantity > 0
    group by ft.account_key, ft.fund_key
),

-- Total proceeds received per (account, fund) across all SELL and SWITCH_OUT trades.
sell_proceeds as (
    select
        ft.account_key,
        ft.fund_key,
        sum(abs(ft.value_gbp)) as total_proceeds_gbp
    from {{ ref('fct_transactions') }} ft
    inner join {{ ref('dim_transaction_type') }} dtt on dtt.transaction_type_key = ft.transaction_type_key
    where dtt.transaction_type in ('SELL', 'SWITCH_OUT')
      and ft.fund_key is not null
      and ft.quantity > 0
    group by ft.account_key, ft.fund_key
),

-- Joins holdings to dims and cost basis; nets buys against sells, floored at zero.
valued as (
    select
        da.account_name,
        df.fund_name,
        hl.valuation_date,
        hl.units_held,
        hl.fund_price_gbp,
        hl.value_gbp,
        greatest(
            coalesce(bc.total_cost_gbp, 0) - coalesce(sp.total_proceeds_gbp, 0),
            0
        ) as cost_basis_gbp
    from holdings_latest hl
    inner join {{ ref('dim_account') }} da  on da.account_key = hl.account_key
    inner join {{ ref('dim_fund') }}    df  on df.fund_key    = hl.fund_key
    left join  buy_cost      bc  on bc.account_key  = hl.account_key and bc.fund_key  = hl.fund_key
    left join  sell_proceeds sp  on sp.account_key  = hl.account_key and sp.fund_key  = hl.fund_key
)

select
    account_name,
    fund_name,
    valuation_date,
    units_held,
    round(fund_price_gbp, 4)                                                              as fund_price_gbp,
    round(value_gbp, 2)                                                                   as value_gbp,
    round(cost_basis_gbp, 2)                                                              as cost_basis_gbp,
    round(value_gbp - cost_basis_gbp, 2)                                                  as unrealised_gain_gbp,
    case
        when cost_basis_gbp > 0
        then round((value_gbp - cost_basis_gbp) / cost_basis_gbp * 100.0, 2)
        else 0.0
    end                                                                                   as unrealised_gain_pct,
    round(value_gbp / sum(value_gbp) over (partition by account_name) * 100.0, 2)         as weight_pct

from valued
order by account_name, fund_name desc
