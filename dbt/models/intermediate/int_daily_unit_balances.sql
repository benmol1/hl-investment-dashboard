-- Forward-fills the sparse trade-date unit balances to every calendar day.
-- Uses DuckDB's ASOF JOIN: for each (account, fund, date) in fund_account_dates,
-- it finds the row in int_cumulative_unit_balances with the largest trade_date
-- that is still <= the calendar date. This is the correct and efficient way to
-- carry a position forward without generating one transaction row per day.
--
-- Note: ASOF JOIN is a DuckDB-specific feature. The equality conditions
-- (account_id, fund_id) define the partition; the inequality (date >= trade_date)
-- defines the "as of" lookup direction.

{{ config(materialized='table') }}

with fund_account_dates as (
    select
        d.date,
        pairs.account_id,
        pairs.fund_id
    from {{ ref('dim_date') }} d
    cross join (
        select distinct account_id, fund_id
        from {{ ref('int_cumulative_unit_balances') }}
    ) pairs
    where d.date >= (select min(trade_date) from {{ ref('int_cumulative_unit_balances') }})
      and d.date <= current_date
)

select
    fd.date,
    fd.account_id,
    fd.fund_id,
    r.units_held

from fund_account_dates fd
asof join {{ ref('int_cumulative_unit_balances') }} r
    on  fd.account_id = r.account_id
    and fd.fund_id    = r.fund_id
    and fd.date       >= r.trade_date
