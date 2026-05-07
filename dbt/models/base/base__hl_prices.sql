{{ config(materialized='view') }}

select
    fund_id,
    date as price_date,
    price_pence,
    price_pence / 100.0 as price_gbp,
    source

from {{ source('hl_dashboard', 'prices') }}
