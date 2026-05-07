select
    dd.date_key,
    df.fund_key,
    p.price_gbp

from {{ ref('base__hl_prices') }} p
inner join {{ ref('dim_date') }}  dd on dd.date   = p.price_date
inner join {{ ref('dim_fund') }}  df on df.fund_id = p.fund_id
