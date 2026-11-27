-- PELM Will Trust income, fees and income paid out, per valuation month, from the dividends,
-- income and fees ledgers. Amounts are positive; the *_coverage_indicator columns say whether
-- the ledgers behind them were supplied for the month, so a zero can be told from "unknown".
with ledger_totals as (
    select
        year_month,
        sum(case when tx_type = 'DIVIDEND'            then amount_gbp else 0 end) as dividends_gbp,
        sum(case when tx_type = 'INTEREST'            then amount_gbp else 0 end) as interest_gbp,
        sum(case when tx_type = 'FX_COMMISSION'       then -amount_gbp else 0 end) as fx_commission_gbp,
        sum(case when tx_type = 'FEE'                 then -amount_gbp else 0 end) as custody_fee_gbp,
        sum(case when tx_type = 'FEE_VAT'             then -amount_gbp else 0 end) as custody_fee_vat_gbp,
        sum(case when tx_type = 'INCOME_DISTRIBUTION' then -amount_gbp else 0 end) as income_distributed_gbp
    from {{ ref('fct_pelm_transactions') }}
    where category in ('income', 'fee', 'external_flow')
    group by year_month
),

monthly as (
    select
        cov.year_month,
        cov.month_end_date,
        pv.month_end_value_gbp,
        coalesce(lt.dividends_gbp, 0)                                       as dividends_gbp,
        coalesce(lt.interest_gbp, 0)                                        as interest_gbp,
        coalesce(lt.dividends_gbp, 0) + coalesce(lt.interest_gbp, 0)        as income_gbp,
        coalesce(lt.fx_commission_gbp, 0)                                   as fx_commission_gbp,
        coalesce(lt.custody_fee_gbp, 0) + coalesce(lt.custody_fee_vat_gbp, 0) as custody_fees_gbp,
        coalesce(lt.income_distributed_gbp, 0)                              as income_distributed_gbp,
        case when cov.dividends_ledger_covered and cov.income_ledger_covered
             then 'Complete' else 'Incomplete' end                          as income_coverage_indicator,
        case when cov.fees_ledger_covered
             then 'Complete' else 'Incomplete' end                          as fees_coverage_indicator
    from {{ ref('int_pelm_ledger_coverage_monthly') }} cov
    inner join {{ ref('base__pelm_valuations') }} pv on pv.year_month = cov.year_month
    left join ledger_totals lt on lt.year_month = cov.year_month
)

select
    *,
    -- Trailing 12-month income and yield on the month-end value; null unless all 12 months have
    -- their income ledgers.
    case
        when count(*) filter (where income_coverage_indicator = 'Complete') over w12 = 12
        then sum(income_gbp) over w12
    end                                                                     as trailing_12m_income_gbp,
    case
        when count(*) filter (where income_coverage_indicator = 'Complete') over w12 = 12
        then sum(income_gbp) over w12 / nullif(month_end_value_gbp, 0)
    end                                                                     as trailing_12m_income_yield
from monthly
window w12 as (order by year_month rows between 11 preceding and current row)
