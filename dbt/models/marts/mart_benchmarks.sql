with monthly_returns as (
    select
        fb.index_id,
        fb.ticker,
        fb.year_month,
        fb.date_key,
        fb.month_end_level,
        lag(fb.month_end_level) over (partition by fb.index_id order by fb.year_month) as prev_month_end_level,
        case
            when lag(fb.month_end_level) over (partition by fb.index_id order by fb.year_month) is null then null
            else (fb.month_end_level
                  - lag(fb.month_end_level) over (partition by fb.index_id order by fb.year_month))
                 / lag(fb.month_end_level) over (partition by fb.index_id order by fb.year_month)
        end as monthly_return
    from {{ ref('fct_benchmarks_monthly') }} fb
),

trailing_returns as (
    select
        mr.index_id,
        mr.ticker,
        mr.year_month,
        dd.date                                                as month_end_date,
        mr.month_end_level,
        mr.prev_month_end_level,
        mr.monthly_return,
        case
            when count(*) over (
                partition by mr.index_id
                order by mr.year_month
                rows between 11 preceding and current row
            ) < 12 then null
            else exp(sum(ln(1 + mr.monthly_return)) over (
                partition by mr.index_id
                order by mr.year_month
                rows between 11 preceding and current row
            )) - 1
        end as trailing_12m_return,
        -- Annualised: (1 + r_36m)^(1/3) - 1
        case
            when count(*) over (
                partition by mr.index_id
                order by mr.year_month
                rows between 35 preceding and current row
            ) < 36 then null
            else power(exp(sum(ln(1 + mr.monthly_return)) over (
                partition by mr.index_id
                order by mr.year_month
                rows between 35 preceding and current row
            )), 1.0 / 3.0) - 1
        end as trailing_36m_return_annualised,

        -- Sharpe ratios: (mean monthly return / stddev of monthly returns) * sqrt(12)
        -- Risk-free rate assumed zero. Null when stddev is zero (flat returns) or insufficient history.
        case
            when count(*) over (
                partition by mr.index_id
                order by mr.year_month
                rows between 11 preceding and current row
            ) < 12 then null
            when stddev_samp(mr.monthly_return) over (
                partition by mr.index_id
                order by mr.year_month
                rows between 11 preceding and current row
            ) = 0 then null
            else (
                avg(mr.monthly_return) over (
                    partition by mr.index_id
                    order by mr.year_month
                    rows between 11 preceding and current row
                )
                / stddev_samp(mr.monthly_return) over (
                    partition by mr.index_id
                    order by mr.year_month
                    rows between 11 preceding and current row
                )
            ) * sqrt(12)
        end as trailing_12m_sharpe,

        case
            when count(*) over (
                partition by mr.index_id
                order by mr.year_month
                rows between 35 preceding and current row
            ) < 36 then null
            when stddev_samp(mr.monthly_return) over (
                partition by mr.index_id
                order by mr.year_month
                rows between 35 preceding and current row
            ) = 0 then null
            else (
                avg(mr.monthly_return) over (
                    partition by mr.index_id
                    order by mr.year_month
                    rows between 35 preceding and current row
                )
                / stddev_samp(mr.monthly_return) over (
                    partition by mr.index_id
                    order by mr.year_month
                    rows between 35 preceding and current row
                )
            ) * sqrt(12)
        end as trailing_36m_sharpe

    from monthly_returns mr
    inner join {{ ref('dim_date') }} dd on dd.date_key = mr.date_key
    where mr.prev_month_end_level is not null  -- first month per index has no prior period
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
