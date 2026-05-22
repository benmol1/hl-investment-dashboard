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
    a.user_id,
    a.provider_id,
    du.user_key,
    dp.provider_key,
    aod.account_open_date

from {{ source('hl_dashboard', 'accounts') }} a
left join account_open_dates aod on aod.account_id = a.id
left join {{ ref('dim_user') }}     du on du.user_id     = a.user_id
left join {{ ref('dim_provider') }} dp on dp.provider_id = a.provider_id
