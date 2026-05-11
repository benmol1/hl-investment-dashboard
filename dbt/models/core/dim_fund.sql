with daily_unit_deltas as (
    select
        fund_id,
        trade_date,
        sum(case
            when transaction_type in ('BUY', 'SWITCH_IN')  then  quantity
            when transaction_type in ('SELL', 'SWITCH_OUT') then -quantity
        end) as unit_delta
    from {{ ref('base__hl_transactions') }}
    where transaction_type in ('BUY', 'SELL', 'SWITCH_IN', 'SWITCH_OUT')
      and fund_id is not null
    group by fund_id, trade_date
),

cumulative_units as (
    select
        fund_id,
        trade_date,
        sum(unit_delta) over (
            partition by fund_id
            order by trade_date
        ) as cumulative_units
    from daily_unit_deltas
),

first_investment_dates as (
    select
        fund_id,
        min(trade_date) as first_investment_date
    from {{ ref('base__hl_transactions') }}
    where transaction_type in ('BUY', 'SWITCH_IN')
      and fund_id is not null
    group by fund_id
),

fund_position_dates as (
    select
        cu.fund_id,
        fid.first_investment_date,
        case
            when max(cu.cumulative_units) > 0.0001 then null
            else max(case when cu.cumulative_units > 0.0001 then cu.trade_date end)
        end as last_position_date
    from cumulative_units cu
    left join first_investment_dates fid on fid.fund_id = cu.fund_id
    group by cu.fund_id, fid.first_investment_date
)

select
    {{ dbt_utils.generate_surrogate_key(['f.id']) }} as fund_key,
    f.id                                             as fund_id,
    f.name                                           as fund_name,
    f.morningstar_code,
    fpd.first_investment_date,
    fpd.last_position_date,
    case when fpd.last_position_date is null then 'Holding' else 'Exited' end as investment_status_indicator

from {{ source('hl_dashboard', 'funds') }} f
left join fund_position_dates fpd on fpd.fund_id = f.id
