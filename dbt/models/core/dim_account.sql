with account_open_dates as (
    select
        account_id,
        min(trade_date) as account_open_date
    from {{ ref('base__hl_transactions') }}
    group by account_id
),

hl_accounts as (
    select
        a.id                as account_name,
        aod.account_open_date,
        'daily'             as data_grain
    from {{ source('hl_dashboard', 'accounts') }} a
    left join account_open_dates aod on aod.account_id = a.id
),

-- PELM is valuation-only (month-end snapshots, no holdings or transactions). The row only
-- exists once pelm_monthly has data, so an empty seed leaves the dimension unchanged.
pelm_account as (
    select
        'PELM'              as account_name,
        min(month_end_date) as account_open_date,
        'monthly'           as data_grain
    from {{ ref('base__pelm_valuations') }}
    having count(*) > 0
),

all_accounts as (
    select * from hl_accounts
    union all
    select * from pelm_account
)

select
    {{ dbt_utils.generate_surrogate_key(['account_name']) }} as account_key,
    account_name,
    account_open_date,
    data_grain

from all_accounts
