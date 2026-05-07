with distinct_types as (
    select distinct
        transaction_type,
        transaction_subtype,
        is_trade,
        is_contribution
    from {{ ref('base__hl_transactions') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['transaction_type', 'transaction_subtype']) }} as transaction_type_key,
    transaction_type,
    transaction_subtype,
    case when is_trade        then 'Trade'        else 'Non-Trade'        end as trade_indicator,
    case when is_contribution then 'Contribution' else 'Non-Contribution' end as contribution_indicator

from distinct_types
