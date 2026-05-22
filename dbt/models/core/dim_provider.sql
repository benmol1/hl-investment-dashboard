select
    {{ dbt_utils.generate_surrogate_key(['p.id']) }} as provider_key,
    p.id                                             as provider_id,
    p.name                                           as provider_name

from {{ source('hl_dashboard', 'providers') }} p
