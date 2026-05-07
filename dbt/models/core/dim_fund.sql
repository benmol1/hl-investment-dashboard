select
    {{ dbt_utils.generate_surrogate_key(['id']) }} as fund_key,
    id                                             as fund_id,
    name                                           as fund_name,
    morningstar_code

from {{ source('hl_dashboard', 'funds') }}
