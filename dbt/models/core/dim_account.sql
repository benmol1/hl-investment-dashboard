with account_open_dates as (
    select
        account_id,
        min(trade_date) as account_open_date
    from {{ ref('base__hl_transactions') }}
    group by account_id
)

select
    {{ dbt_utils.generate_surrogate_key(['a.id']) }} as account_key,
    a.id                                             as account_name,
    a.account_type,
    a.provider_id,
    a.user_id,
    aod.account_open_date

from {{ source('hl_dashboard', 'accounts') }} a
left join account_open_dates aod on aod.account_id = a.id
