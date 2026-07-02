with
-- Month-end fund value per (account, fund). Only present for months the fund
-- was actually held — funds fall out of fct_holdings_daily once fully sold,
-- so no spine is needed here (unlike the account-level snapshot, which always
-- has a value once the account is open).
month_end_values as (
    select
        fdh.account_key,
        fdh.fund_key,
        dd.year_month,
        max(dd.financial_year) as financial_year,
        dd.date                as month_end_date,
        sum(fdh.value_gbp)     as month_end_value_gbp
    from {{ ref('fct_holdings_daily') }} fdh
    inner join {{ ref('dim_date') }} dd on dd.date_key = fdh.date_key
    where dd.month_end_indicator = 'Month End'
      and fdh.holding_type = 'Fund'
    group by fdh.account_key, fdh.fund_key, dd.year_month, dd.date
),

-- Net fund trades (buy value minus sell proceeds) within each month, per
-- (account, fund). Switches count as flows here too — a switch isn't fund
-- performance, so it should be excluded the same way a contribution is.
monthly_fund_flows as (
    select
        ft.account_key,
        ft.fund_key,
        dd.year_month,
        sum(case when dtt.transaction_type in ('BUY', 'SWITCH_IN')
                 then abs(ft.value_gbp) else 0 end)
        - sum(case when dtt.transaction_type in ('SELL', 'SWITCH_OUT')
                   then abs(ft.value_gbp) else 0 end) as monthly_net_fund_flows_gbp
    from {{ ref('fct_transactions') }} ft
    inner join {{ ref('dim_transaction_type') }} dtt on dtt.transaction_type_key = ft.transaction_type_key
    inner join {{ ref('dim_date') }} dd on dd.date_key = ft.trade_date_key
    where dtt.trade_indicator = 'Trade'
      and ft.fund_key is not null
    group by ft.account_key, ft.fund_key, dd.year_month
)

select
    da.account_name,
    df.fund_name,
    df.fund_short_name,
    mev.year_month,
    mev.financial_year,
    mev.month_end_date,
    mev.month_end_value_gbp,
    coalesce(mff.monthly_net_fund_flows_gbp, 0) as monthly_net_fund_flows_gbp
from month_end_values mev
inner join {{ ref('dim_account') }} da on da.account_key = mev.account_key
inner join {{ ref('dim_fund') }}    df on df.fund_key    = mev.fund_key
left join monthly_fund_flows mff
    on  mff.account_key = mev.account_key
    and mff.fund_key    = mev.fund_key
    and mff.year_month  = mev.year_month
order by da.account_name, df.fund_name, mev.year_month
