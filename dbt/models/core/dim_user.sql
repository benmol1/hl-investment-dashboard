select
    {{ dbt_utils.generate_surrogate_key(['u.id']) }} as user_key,
    u.id                                             as user_id,
    u.username,
    u.role,
    u.display_name

from {{ source('hl_dashboard', 'users') }} u
