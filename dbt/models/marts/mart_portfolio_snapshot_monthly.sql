with
-- Last month for which each monthly-grain account (PELM) has a valuation. Its spine stops here
-- rather than running to today, since the source only updates quarterly.
monthly_grain_last_date as (
    select
        'PELM'             as account_name,
        max(month_end_date) as last_valuation_date
    from {{ ref('base__pelm_valuations') }}
),

-- All (account, month) combinations since account open, up to but not including the current month.
account_month_spine as (
    select
        da.account_key,
        da.account_name,
        da.data_grain,
        dd.year_month,
        max(dd.financial_year) as financial_year
    from {{ ref('dim_account') }} da
    inner join {{ ref('dim_date') }} dd
        on  dd.date >= da.account_open_date
        and dd.date < date_trunc('month', current_date)
    left join monthly_grain_last_date mgl on mgl.account_name = da.account_name
    where da.data_grain = 'daily'
       or dd.date <= last_day(mgl.last_valuation_date)
    group by da.account_key, da.account_name, da.data_grain, dd.year_month
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

    union all

    -- PELM supplies month-end values directly from the Barratt & Cooke valuations file.
    select
        da.account_key,
        pv.year_month,
        pv.month_end_date,
        pv.month_end_value_gbp
    from {{ ref('base__pelm_valuations') }} pv
    inner join {{ ref('dim_account') }} da on da.account_name = 'PELM'
),

-- Cash inflows (contributions + transfers) received within each month.
monthly_inflows as (
    select
        ft.account_key,
        dd.year_month,
        sum(ft.value_gbp) as month_total_inflows_gbp
    from {{ ref('fct_transactions') }} ft
    inner join {{ ref('dim_transaction_type') }} dtt on dtt.transaction_type_key = ft.transaction_type_key
    inner join {{ ref('dim_date') }} dd on dd.date_key = ft.trade_date_key
    where dtt.contribution_indicator in ('Contribution', 'Transfer')
    group by ft.account_key, dd.year_month

    union all

    -- PELM external flows come from the ledger: cash transferred in, capital withdrawals, and the
    -- BACS payments of income to the beneficiary. Flows on or before the first valuation date are
    -- already inside the opening value, so they are left out.
    select
        da.account_key,
        t.year_month,
        sum(t.amount_gbp)
    from {{ ref('fct_pelm_transactions') }} t
    inner join {{ ref('dim_account') }} da on da.account_name = 'PELM'
    where t.category = 'external_flow'
      and t.amount_gbp is not null
      and t.tx_date > (select min(valuation_date) from {{ ref('base__pelm_valuations') }})
    group by da.account_key, t.year_month
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
),

-- PELM cash at each month-end: every sub-ledger's opening balance plus every cash movement up to
-- that date. Deposit and settlement sweeps are left out because they move cash between parts of
-- the trust (the capital ledger itself runs at about zero). Null for months before the ledger
-- starts.
pelm_cash as (
    select
        ams.account_key,
        ams.year_month,
        sum(t.amount_gbp) as cash_balance_gbp
    from account_month_spine ams
    inner join {{ ref('fct_pelm_transactions') }} t
        on  t.category <> 'internal_transfer'
        and t.tx_date <= last_day(cast(ams.year_month || '-01' as date))
    where ams.data_grain = 'monthly'
    group by ams.account_key, ams.year_month
)

select
    ams.account_name,
    ams.year_month,
    ams.financial_year,
    mev.month_end_date,
    mev.month_end_value_gbp,
    coalesce(mi.month_total_inflows_gbp, 0)          as monthly_inflows_gbp,
    -- Null for PELM: there are no fund trades in the model, so zero would be misleading.
    case when ams.data_grain = 'monthly' then null
         else coalesce(mfp.net_fund_purchases_gbp, 0)
    end                                                as monthly_net_fund_purchases_gbp,
    -- PELM only; null for the daily-grain accounts.
    pc.cash_balance_gbp,
    mev.month_end_value_gbp - pc.cash_balance_gbp      as invested_value_gbp,
    -- HL accounts have every transaction. PELM is only complete where the ledgers holding its
    -- external flows were supplied; elsewhere income paid out is missing and the return is low.
    case when ams.data_grain = 'monthly'
         then coalesce(cov.cash_flow_coverage_indicator, 'Incomplete')
         else 'Complete'
    end                                                as cash_flow_coverage_indicator
from account_month_spine ams
left join month_end_values mev
    on  mev.account_key = ams.account_key
    and mev.year_month  = ams.year_month
left join monthly_inflows mi
    on  mi.account_key  = ams.account_key
    and mi.year_month   = ams.year_month
left join monthly_fund_purchases mfp
    on  mfp.account_key = ams.account_key
    and mfp.year_month  = ams.year_month
left join pelm_cash pc
    on  pc.account_key = ams.account_key
    and pc.year_month  = ams.year_month
left join {{ ref('int_pelm_ledger_coverage_monthly') }} cov
    on  ams.data_grain = 'monthly'
    and cov.year_month = ams.year_month
