with account_fund_pairs as (
    select distinct account_key, fund_key
    from {{ ref('fct_transactions') }}
    where fund_key is not null
),

-- Spine: every (account, fund, date) combination for which a price exists
price_spine as (
    select
        afp.account_key,
        fp.fund_key,
        fp.date_key
    from account_fund_pairs afp
    inner join {{ ref('fct_fund_prices_daily') }} fp using (fund_key)
),

-- Cumulative units held per account/fund as of each price date.
-- Only trade transactions (BUY, SELL, SWITCH_IN, SWITCH_OUT) affect unit balances.
-- Direction is determined by transaction type: buys/switch-ins add units, sells/switch-outs subtract.
cumulative_units as (
    select
        ps.date_key,
        ps.account_key,
        ps.fund_key,
        coalesce(sum(
            case dtt.transaction_type
                when 'BUY'        then  ft.quantity
                when 'SWITCH_IN'  then  ft.quantity
                when 'SELL'       then -ft.quantity
                when 'SWITCH_OUT' then -ft.quantity
            end
        ), 0) as units_held
    from price_spine ps
    left join {{ ref('fct_transactions') }}     ft  on  ft.account_key           = ps.account_key
                                                    and ft.fund_key              = ps.fund_key
                                                    and ft.trade_date_key       <= ps.date_key
    left join {{ ref('dim_transaction_type') }} dtt on  dtt.transaction_type_key = ft.transaction_type_key
    where dtt.trade_indicator = 'Trade'
       or ft.transaction_type_key is null
    group by ps.date_key, ps.account_key, ps.fund_key
),

fund_holdings as (
    select
        cu.date_key,
        cu.account_key,
        cu.fund_key,
        'Fund'                              as holding_type,
        cu.units_held,
        fp.fund_price_gbp,
        cu.units_held * fp.fund_price_gbp   as value_gbp
    from cumulative_units cu
    inner join {{ ref('fct_fund_prices_daily') }} fp on  fp.fund_key = cu.fund_key
                                                     and fp.date_key = cu.date_key
    where cu.units_held > 0
),

cash_holdings as (
    select
        date_key,
        account_key,
        null                            as fund_key,
        'Cash'                          as holding_type,
        null                            as units_held,
        null                            as fund_price_gbp,
        cash_balance_gbp                as value_gbp
    from {{ ref('fct_daily_cash_position') }}
)

select * from fund_holdings
union all
select * from cash_holdings
