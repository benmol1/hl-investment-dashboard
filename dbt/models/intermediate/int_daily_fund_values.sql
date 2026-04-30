{{ config(materialized='table') }}

select
    h.date,
    h.account_id,
    h.fund_id,
    f.name                               as fund_name,
    h.units_held,
    p.price_gbp,
    round(h.units_held * p.price_gbp, 2) as value_gbp

from {{ ref('int_daily_unit_balances') }} h
asof join {{ ref('stg_prices') }} p
    on p.fund_id = h.fund_id
    and p.date  <= h.date
join {{ source('hl_dashboard', 'funds') }} f
    on f.id = h.fund_id

where h.units_held > 0.0001
