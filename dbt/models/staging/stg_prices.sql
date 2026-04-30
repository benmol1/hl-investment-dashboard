select
    fund_id,
    date,
    price_pence,
    price_pence / 100.0 as price_gbp,
    source

from {{ source('hl_dashboard', 'prices') }}
