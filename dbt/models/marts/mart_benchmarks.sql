with monthly_levels as (
    select
        index_id,
        ticker,
        strftime(market_date, '%Y-%m')                          as year_month,
        max(market_date)                                         as month_end_date,
        last(index_level order by market_date)                   as month_end_level
    from {{ ref('base__hl_benchmarks') }}
    group by index_id, ticker, strftime(market_date, '%Y-%m')
),

monthly_returns as (
    select
        index_id,
        ticker,
        year_month,
        month_end_date,
        month_end_level,
        lag(month_end_level) over (partition by index_id order by year_month) as prev_month_end_level,
        case
            when lag(month_end_level) over (partition by index_id order by year_month) is null then null
            else (month_end_level
                  - lag(month_end_level) over (partition by index_id order by year_month))
                 / lag(month_end_level) over (partition by index_id order by year_month)
        end as monthly_return
    from monthly_levels
),

trailing_returns as (
    select
        index_id,
        ticker,
        year_month,
        month_end_date,
        month_end_level,
        prev_month_end_level,
        monthly_return,
        case
            when count(*) over (
                partition by index_id
                order by year_month
                rows between 11 preceding and current row
            ) < 12 then null
            else exp(sum(ln(1 + monthly_return)) over (
                partition by index_id
                order by year_month
                rows between 11 preceding and current row
            )) - 1
        end as trailing_12m_return,
        -- Annualised: (1 + r_36m)^(1/3) - 1
        case
            when count(*) over (
                partition by index_id
                order by year_month
                rows between 35 preceding and current row
            ) < 36 then null
            else power(exp(sum(ln(1 + monthly_return)) over (
                partition by index_id
                order by year_month
                rows between 35 preceding and current row
            )), 1.0 / 3.0) - 1
        end as trailing_36m_return_annualised,

        -- Sharpe ratios: (mean monthly return / stddev of monthly returns) * sqrt(12)
        -- Risk-free rate assumed zero. Null when stddev is zero (flat returns) or insufficient history.
        case
            when count(*) over (
                partition by index_id
                order by year_month
                rows between 11 preceding and current row
            ) < 12 then null
            when stddev_samp(monthly_return) over (
                partition by index_id
                order by year_month
                rows between 11 preceding and current row
            ) = 0 then null
            else (
                avg(monthly_return) over (
                    partition by index_id
                    order by year_month
                    rows between 11 preceding and current row
                )
                / stddev_samp(monthly_return) over (
                    partition by index_id
                    order by year_month
                    rows between 11 preceding and current row
                )
            ) * sqrt(12)
        end as trailing_12m_sharpe,

        case
            when count(*) over (
                partition by index_id
                order by year_month
                rows between 35 preceding and current row
            ) < 36 then null
            when stddev_samp(monthly_return) over (
                partition by index_id
                order by year_month
                rows between 35 preceding and current row
            ) = 0 then null
            else (
                avg(monthly_return) over (
                    partition by index_id
                    order by year_month
                    rows between 35 preceding and current row
                )
                / stddev_samp(monthly_return) over (
                    partition by index_id
                    order by year_month
                    rows between 35 preceding and current row
                )
            ) * sqrt(12)
        end as trailing_36m_sharpe

    from monthly_returns
    where prev_month_end_level is not null  -- first month per index has no prior period
)

select
    index_id,
    ticker,
    year_month,
    month_end_date,
    month_end_level,
    prev_month_end_level,
    monthly_return,
    trailing_12m_return,
    trailing_36m_return_annualised,
    trailing_12m_sharpe,
    trailing_36m_sharpe
from trailing_returns
order by index_id, year_month
