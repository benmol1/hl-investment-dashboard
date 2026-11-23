{{ config(materialized='view') }}

-- Barratt & Cooke date valuations on the last working day of the month. Everything else in the
-- model (dim_date, benchmarks, the HL accounts) uses calendar month-ends, so map onto those. A
-- day or two is immaterial for a long-term series, and it lets PELM line up without special cases.
select
    last_day(cast(month_end_date as date))          as month_end_date,
    cast(month_end_date as date)                    as valuation_date,
    strftime(cast(month_end_date as date), '%Y-%m') as year_month,
    cast(value_gbp as double)                       as month_end_value_gbp,
    coalesce(cast(external_flow_gbp as double), 0)  as external_flow_gbp

from {{ ref('pelm_monthly') }}
