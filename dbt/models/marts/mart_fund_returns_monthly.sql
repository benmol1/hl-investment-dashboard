with
-- Pulls EMV, BMV (prior month-end value), and net flow cash flows from the fund-level snapshot.
monthly_inputs as (
    select
        account_name,
        fund_name,
        fund_short_name,
        year_month,
        financial_year,
        month_end_date,
        month_end_value_gbp                                                                              as emv,
        lag(month_end_value_gbp) over (partition by account_name, fund_name order by year_month)          as bmv,
        monthly_net_fund_flows_gbp                                                                        as cf
    from {{ ref('mart_fund_snapshot_monthly') }}
),

-- Calculates Modified Dietz return for each (account, fund, month); nulls out
-- the first month held (no prior BMV — e.g. a brand-new position).
monthly_returns as (
    select
        account_name,
        fund_name,
        fund_short_name,
        year_month,
        financial_year,
        month_end_date,
        emv,
        bmv,
        cf,
        -- Modified Dietz: (EMV - BMV - CF) / (BMV + 0.5 * CF), mid-period cash flow weighting
        case
            when (bmv + 0.5 * cf) = 0 then null
            else (emv - bmv - cf) / (bmv + 0.5 * cf)
        end as monthly_return
    from monthly_inputs
    where bmv is not null  -- first month held has no prior period
)

select
    account_name,
    fund_name,
    fund_short_name,
    year_month,
    financial_year,
    month_end_date,
    emv as month_end_value_gbp,
    bmv as prev_month_end_value_gbp,
    cf  as month_net_flows_gbp,
    monthly_return
from monthly_returns
