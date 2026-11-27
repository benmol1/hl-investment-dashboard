-- For each PELM valuation month, which Barratt & Cooke sub-ledgers were supplied for the whole
-- month. External cash flows sit in two of them: capital withdrawals and transfers in the capital
-- ledger, and BACS income payments to the beneficiary in the dividends ledger. A month's flows
-- (and so its return) are only complete when both cover it.
with months as (
    select
        year_month,
        cast(year_month || '-01' as date)                       as month_start_date,
        month_end_date,
        year_month = min(year_month) over ()                    as is_first_month
    from {{ ref('base__pelm_valuations') }}
),

covered as (
    -- A statement covers a month if it spans it. The first valuation month counts as covered by
    -- a statement starting within it: the account opened that month, so nothing came before.
    select
        m.year_month,
        c.ledger
    from months m
    inner join {{ ref('base__pelm_ledger_coverage') }} c
        on  c.period_end >= m.month_end_date
        and (c.period_start <= m.month_start_date
             or (m.is_first_month and c.period_start <= m.month_end_date))
    group by m.year_month, c.ledger
)

select
    m.year_month,
    m.month_end_date,
    bool_or(cv.ledger = 'capital')   is true                    as capital_ledger_covered,
    bool_or(cv.ledger = 'dividends') is true                    as dividends_ledger_covered,
    bool_or(cv.ledger = 'income')    is true                    as income_ledger_covered,
    bool_or(cv.ledger = 'fees')      is true                    as fees_ledger_covered,
    case
        when bool_or(cv.ledger = 'capital') and bool_or(cv.ledger = 'dividends') then 'Complete'
        else 'Incomplete'
    end                                                          as cash_flow_coverage_indicator
from months m
left join covered cv on cv.year_month = m.year_month
group by m.year_month, m.month_end_date
