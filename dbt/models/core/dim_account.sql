select
    {{ dbt_utils.generate_surrogate_key(['id']) }} as account_key,
    id                                             as account_name

from {{ source('hl_dashboard', 'accounts') }}
