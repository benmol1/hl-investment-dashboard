-- A table, not a view: the source is read from a relative file path, which a view would
-- re-resolve against whatever directory later queries it from.
{{ config(materialized='table') }}

-- Barratt & Cooke date valuations on the last working day of the month. Everything else in the
-- model (dim_date, benchmarks, the HL accounts) uses calendar month-ends, so map onto those. A
-- day or two is immaterial for a long-term series, and it lets PELM line up without special cases.
-- External cash flows are not in this file: they come from the ledger (fct_pelm_transactions).
select
    last_day(cast(month_end_date as date))          as month_end_date,
    cast(month_end_date as date)                    as valuation_date,
    strftime(cast(month_end_date as date), '%Y-%m') as year_month,
    cast(value_gbp as double)                       as month_end_value_gbp

from ({{ pelm_monthly_source() }}) as pelm
