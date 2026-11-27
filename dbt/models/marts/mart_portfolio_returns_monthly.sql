with
-- Pulls EMV, BMV (prior month-end value), and contribution cash flows from the monthly snapshot.
monthly_inputs as (
    select
        account_name,
        year_month,
        financial_year,
        month_end_date,
        month_end_value_gbp                                                         as emv,
        lag(month_end_value_gbp) over (partition by account_name order by year_month) as bmv,
        monthly_inflows_gbp                                                          as cf,
        monthly_income_distributed_gbp                                               as income_out,
        cash_flow_coverage_indicator
    from {{ ref('mart_portfolio_snapshot_monthly') }}
),

-- Calculates Modified Dietz return for each month; nulls out the first month per account (no prior BMV).
monthly_returns as (
    select
        account_name,
        year_month,
        financial_year,
        month_end_date,
        emv,
        bmv,
        cf,
        cash_flow_coverage_indicator,
        -- Modified Dietz: (EMV - BMV - CF) / (BMV + 0.5 * CF), mid-period cash flow weighting
        case
            when (bmv + 0.5 * cf) = 0 then null
            else (emv - bmv - cf) / (bmv + 0.5 * cf)
        end as monthly_return,
        -- PELM only: the same return without the income paid out to the beneficiary, i.e. what
        -- the return looks like when the income data is missing. Null for ISA/SIPP.
        case
            when income_out is null or (bmv + 0.5 * (cf + income_out)) = 0 then null
            else (emv - bmv - (cf + income_out)) / (bmv + 0.5 * (cf + income_out))
        end as monthly_return_excl_income_out
    from monthly_inputs
    where bmv is not null  -- first month per account has no prior period
),

-- Average uplift the income data adds to the monthly return, measured over the months that have
-- it (PELM months with complete cash flows). Used to estimate the months that don't.
income_uplift as (
    select
        account_name,
        avg(monthly_return - monthly_return_excl_income_out) as avg_income_uplift,
        count(*)                                             as uplift_months
    from monthly_returns
    where cash_flow_coverage_indicator = 'Complete'
      and monthly_return_excl_income_out is not null
    group by account_name
),

monthly_estimates as (
    select
        mr.*,
        iu.avg_income_uplift,
        -- Best estimate of the total return: the actual return where cash flows are complete;
        -- otherwise the actual return plus the average income uplift.
        case
            when mr.cash_flow_coverage_indicator = 'Incomplete' and iu.avg_income_uplift is not null
            then mr.monthly_return + iu.avg_income_uplift
            else mr.monthly_return
        end as estimated_monthly_return
    from monthly_returns mr
    left join income_uplift iu on iu.account_name = mr.account_name
),

-- Compounds monthly returns into 12m and 36m trailing windows; adds annualised Sharpe ratios.
trailing_returns as (
    select
        account_name,
        year_month,
        financial_year,
        month_end_date,
        emv as month_end_value_gbp,
        bmv as prev_month_end_value_gbp,
        cf  as month_inflows_gbp,
        monthly_return,
        cash_flow_coverage_indicator,
        estimated_monthly_return,
        avg_income_uplift,
        case
            when count(*) over (
                partition by account_name
                order by year_month
                rows between 11 preceding and current row
            ) < 12 then null
            else exp(sum(ln(1 + monthly_return)) over (
                partition by account_name
                order by year_month
                rows between 11 preceding and current row
            )) - 1
        end as trailing_12m_return,
        -- Annualised: (1 + r_36m)^(1/3) - 1
        case
            when count(*) over (
                partition by account_name
                order by year_month
                rows between 35 preceding and current row
            ) < 36 then null
            else power(exp(sum(ln(1 + monthly_return)) over (
                partition by account_name
                order by year_month
                rows between 35 preceding and current row
            )), 1.0 / 3.0) - 1
        end as trailing_36m_return_annualised,

        -- Sharpe ratios: (mean monthly return / stddev of monthly returns) * sqrt(12)
        -- Risk-free rate assumed zero. Null when stddev is zero (flat returns) or insufficient history.
        case
            when count(*) over (
                partition by account_name
                order by year_month
                rows between 11 preceding and current row
            ) < 12 then null
            when stddev_samp(monthly_return) over (
                partition by account_name
                order by year_month
                rows between 11 preceding and current row
            ) = 0 then null
            else (
                avg(monthly_return) over (
                    partition by account_name
                    order by year_month
                    rows between 11 preceding and current row
                )
                / stddev_samp(monthly_return) over (
                    partition by account_name
                    order by year_month
                    rows between 11 preceding and current row
                )
            ) * sqrt(12)
        end as trailing_12m_sharpe,

        case
            when count(*) over (
                partition by account_name
                order by year_month
                rows between 35 preceding and current row
            ) < 36 then null
            when stddev_samp(monthly_return) over (
                partition by account_name
                order by year_month
                rows between 35 preceding and current row
            ) = 0 then null
            else (
                avg(monthly_return) over (
                    partition by account_name
                    order by year_month
                    rows between 35 preceding and current row
                )
                / stddev_samp(monthly_return) over (
                    partition by account_name
                    order by year_month
                    rows between 35 preceding and current row
                )
            ) * sqrt(12)
        end as trailing_36m_sharpe

    from monthly_estimates
)

select
    account_name,
    year_month,
    financial_year,
    month_end_date,
    month_end_value_gbp,
    prev_month_end_value_gbp,
    month_inflows_gbp,
    monthly_return,
    cash_flow_coverage_indicator,
    estimated_monthly_return,
    avg_income_uplift,
    trailing_12m_return,
    trailing_36m_return_annualised,
    trailing_12m_sharpe,
    trailing_36m_sharpe
from trailing_returns
