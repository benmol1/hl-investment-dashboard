with
-- All (account, month) combinations since account open, up to but not including the current month.
account_month_spine as (
    select
        da.account_key,
        da.account_name,
        dd.year_month,
        max(dd.financial_year) as financial_year
    from {{ ref('dim_account') }} da
    inner join {{ ref('dim_date') }} dd
        on  dd.date >= da.account_open_date
        and dd.date < date_trunc('month', current_date)
    group by da.account_key, da.account_name, dd.year_month
),

-- Total portfolio value on the last trading day of each month.
month_end_values as (
    select
        fdh.account_key,
        dd.year_month,
        dd.date                as month_end_date,
        sum(fdh.value_gbp)     as month_end_value_gbp
    from {{ ref('fct_holdings_daily') }} fdh
    inner join {{ ref('dim_date') }} dd on dd.date_key = fdh.date_key
    where dd.month_end_indicator = 'Month End'
    group by fdh.account_key, dd.year_month, dd.date
),

-- Cash contributions received within each month.
monthly_contributions as (
    select
        ft.account_key,
        dd.year_month,
        sum(ft.value_gbp) as month_total_contributions_gbp
    from {{ ref('fct_transactions') }} ft
    inner join {{ ref('dim_transaction_type') }} dtt on dtt.transaction_type_key = ft.transaction_type_key
    inner join {{ ref('dim_date') }} dd on dd.date_key = ft.trade_date_key
    where dtt.contribution_indicator in ('Contribution', 'Transfer')
    group by ft.account_key, dd.year_month
),

-- Net fund trades (buy value minus sell proceeds) within each month.
monthly_fund_purchases as (
    select
        ft.account_key,
        dd.year_month,
        sum(case when dtt.transaction_type in ('BUY', 'SWITCH_IN')
                 then abs(ft.value_gbp) else 0 end)
        - sum(case when dtt.transaction_type in ('SELL', 'SWITCH_OUT')
                   then abs(ft.value_gbp) else 0 end) as net_fund_purchases_gbp
    from {{ ref('fct_transactions') }} ft
    inner join {{ ref('dim_transaction_type') }} dtt on dtt.transaction_type_key = ft.transaction_type_key
    inner join {{ ref('dim_date') }} dd on dd.date_key = ft.trade_date_key
    where dtt.trade_indicator = 'Trade'
    group by ft.account_key, dd.year_month
)

select
    ams.account_name,
    ams.year_month,
    ams.financial_year,
    mev.month_end_date,
    mev.month_end_value_gbp,
    coalesce(mc.month_total_contributions_gbp, 0)        as monthly_contributions_gbp,
    coalesce(mfp.net_fund_purchases_gbp, 0)              as monthly_net_fund_purchases_gbp
from account_month_spine ams
left join month_end_values mev
    on  mev.account_key = ams.account_key
    and mev.year_month  = ams.year_month
left join monthly_contributions mc
    on  mc.account_key  = ams.account_key
    and mc.year_month   = ams.year_month
left join monthly_fund_purchases mfp
    on  mfp.account_key = ams.account_key
    and mfp.year_month  = ams.year_month
