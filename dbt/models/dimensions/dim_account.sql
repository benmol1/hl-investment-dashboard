select
    row_number() over (order by id) as account_key,
    id                              as account_id

from {{ source('hl_dashboard', 'accounts') }}
