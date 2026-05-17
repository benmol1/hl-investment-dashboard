with account_fund_min_dates as (
    select account_key, fund_key, min(trade_date_key) as min_date_key
    from {{ ref('fct_transactions') }}
    where fund_key is not null
    group by account_key, fund_key
),

-- Spine: every (account, fund, calendar date) from that account/fund's first transaction to today
fund_date_spine as (
    select
        afmd.account_key,
        afmd.fund_key,
        dd.date_key
    from account_fund_min_dates afmd
    inner join {{ ref('dim_date') }} dd
        on  dd.date_key >= afmd.min_date_key
        and dd.date     <= current_date
),

-- Signed unit deltas aggregated to one row per (account, fund, trade date)
unit_deltas as (
    select
        ft.account_key,
        ft.fund_key,
        ft.trade_date_key,
        sum(
            case dtt.transaction_type
                when 'BUY'        then  ft.quantity
                when 'SWITCH_IN'  then  ft.quantity
                when 'SELL'       then -ft.quantity
                when 'SWITCH_OUT' then -ft.quantity
            end
        ) as unit_delta
    from {{ ref('fct_transactions') }}           ft
    inner join {{ ref('dim_transaction_type') }} dtt on dtt.transaction_type_key = ft.transaction_type_key
    where dtt.trade_indicator = 'Trade'
      and ft.fund_key is not null
    group by ft.account_key, ft.fund_key, ft.trade_date_key
),

-- Running cumulative units as of each trade date (sparse — trade dates only)
cumulative_at_trade_dates as (
    select
        account_key,
        fund_key,
        trade_date_key,
        sum(unit_delta) over (
            partition by account_key, fund_key
            order by trade_date_key
        ) as units_held
    from unit_deltas
),

-- Forward-fill units to every calendar date using ASOF join
units_daily as (
    select
        fds.date_key,
        fds.account_key,
        fds.fund_key,
        coalesce(cu.units_held, 0) as units_held
    from fund_date_spine fds
    asof left join cumulative_at_trade_dates cu
        on  cu.account_key     = fds.account_key
        and cu.fund_key        = fds.fund_key
        and cu.trade_date_key <= fds.date_key
)

select
    ud.date_key,
    ud.account_key,
    ud.fund_key,
    ud.units_held,
    fp.fund_price_gbp,
    ud.units_held * fp.fund_price_gbp as value_gbp
from units_daily ud
asof join {{ ref('fct_fund_prices_daily') }} fp
    on  fp.fund_key   = ud.fund_key
    and fp.date_key  <= ud.date_key
where ud.units_held > 0.0001  -- threshold filters rounding errors from closed positions
