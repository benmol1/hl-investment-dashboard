with monthly_inputs as (
    select
        account_id,
        year_month,
        financial_year,
        month_end_date,
        month_end_value_gbp                                                         as emv,
        lag(month_end_value_gbp) over (partition by account_id order by year_month) as bmv,
        month_total_contributions_gbp                                                as cf
    from {{ ref('mart_monthly_snapshot') }}
),

monthly_returns as (
    select
        account_id,
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
    where bmv is not null  -- first month per account has no prior period
),

trailing_returns as (
    select
        account_id,
        year_month,
        financial_year,
        month_end_date,
        emv as month_end_value_gbp,
        bmv as prev_month_end_value_gbp,
        cf  as month_contributions_gbp,
        monthly_return,
        case
            when count(*) over (
                partition by account_id
                order by year_month
                rows between 11 preceding and current row
            ) < 12 then null
            else exp(sum(ln(1 + monthly_return)) over (
                partition by account_id
                order by year_month
                rows between 11 preceding and current row
            )) - 1
        end as trailing_12m_return,
        -- Annualised: (1 + r_36m)^(1/3) - 1
        case
            when count(*) over (
                partition by account_id
                order by year_month
                rows between 35 preceding and current row
            ) < 36 then null
            else power(exp(sum(ln(1 + monthly_return)) over (
                partition by account_id
                order by year_month
                rows between 35 preceding and current row
            )), 1.0 / 3.0) - 1
        end as trailing_36m_return_annualised
    from monthly_returns
)

select
    account_id,
    year_month,
    financial_year,
    month_end_date,
    month_end_value_gbp,
    prev_month_end_value_gbp,
    month_contributions_gbp,
    monthly_return,
    trailing_12m_return,
    trailing_36m_return_annualised
from trailing_returns
order by account_id, year_month
