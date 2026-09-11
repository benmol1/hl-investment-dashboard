# PELM Will Trust — Integration Plan

*Drafted: 2026-09-11 · Branch: `feature/pelm-will-trust` · Status: proposed, not started*

Adds the **P E L Molyneaux Will Trust** (account `C070982`, managed by Barratt & Cooke)
to the dashboard as a third account alongside the HL ISA and SIPP, so its performance can
be compared against both and against the existing benchmarks.

---

## 1. Source material

Supplied by Barratt & Cooke on 4 June 2026 (see email thread), extracted into `pelm-inputs/`.

| File | Content | Usable? |
|---|---|---|
| `C070982 End of Month Valuations.xlsx` | 33 rows: month-end date + total market value, Sep 2023 → May 2026. Two columns. | Yes — trivially |
| `C070982 Ledger statements.pdf` | 3 pages, GIA cash ledger 4 Sep 2023 – 4 Jun 2026. Buys/sells with consideration, transfers in/out, one BACS payment out. | Partly — text extraction shuffles the debit/credit columns; read by hand |
| `C070982 Breakdown 2023-2024 … 2026.pdf` | Per-transaction commission / stamp duty / PTM levy, plus fund OCF rates. 4–7 pages each. | Not worth parsing |

The original `fwdportfoliohistoricaldata.zip` has been removed; the six files above are its
contents.

### Three findings that drive the design

**1. The portfolio is a single number, not a holdings list.**
The valuations file carries no per-security breakdown, and the ledger records the inception
in-specie transfers as bare quantities — `13500 THE RENEWABLES INFR`, `2025 BRITISH LAND
ORD` — with **no value attached**. Daily security-level holdings cannot be reconstructed
from this data at any level of effort.

**2. There are material external cash flows that must not be read as performance.**
The £140k fall between Apr and May 2025 is a `BACS Payment *3850` of **£157,000** on
21 May 2025. Inception also brought in £20,679.81 (21 Sep 2023) and £4,774.78
(24 Oct 2023) of cash. Treating the valuation series naively as a return series gives
**−7.0%**; chain-linking with these flows gives **+18.8%**.

**3. The ledger is incomplete — it contains no dividends and no fees.**
Zero matches for DIV / FEE / CHARGE / COMMISSION / MANAGEMENT across all 530 extracted
lines, alongside 16 `TRANSFERRED TO DEPOSIT` entries pointing at a deposit account whose
ledger we were not sent. Our chain-linked figure of **18.8%** sits ~4.6pp below Alastair's
stated total return of **23.4%** for 4 Sep 2023 – 4 Jun 2026. The most likely explanation
is income being swept to the deposit account and excluded from the month-end valuations.
This is resolved by question 1 in §6 and should be settled before the comparison against
ISA/SIPP is published anywhere.

*(Partly offsetting: our series runs 29 Sep 2023 – 29 May 2026, a slightly shorter window
than theirs, so an exact match should not be expected either way.)*

---

## 2. Recommended approach — attach at the monthly-snapshot seam

`mart_portfolio_returns_monthly.sql` reads exactly four fields from
`mart_portfolio_snapshot_monthly.sql`:

    account_name, year_month, month_end_value_gbp, monthly_inflows_gbp

Modified Dietz, trailing 12m/36m returns, Sharpe ratios and the benchmark comparison all
hang off those four fields and nothing lower. PELM supplies two of them directly from the
spreadsheet and the third from the ledger.

**So: union PELM into the monthly snapshot mart and stop there.** No PELM transactions,
holdings, prices, or funds. Everything below the snapshot layer is HL-specific plumbing for
which PELM has no data.

    pelm-inputs/*.xlsx  ->  data/imports/pelm_monthly.csv  ->  dbt seed  --+
                            (month_end_date, value_gbp, external_flow_gbp) |
                                                                           |
    fct_holdings_daily + fct_transactions  ------------------------------->+
                                                                           |
                                                                           v
                                               mart_portfolio_snapshot_monthly
                                                                           |
                                                                           v
                                    returns / benchmarks / overview — unchanged

### Why not model PELM properly?

Reconstructing daily holdings would mean parsing three PDF pages of shuffled columns,
inventing valuations for the in-specie transfers, sourcing daily prices for ~40 individual
equities across four currencies, and maintaining all of it quarterly — to arrive at the
same monthly return series the spreadsheet already gives us. The analytical output is
identical; only the maintenance burden differs.

---

## 3. Implementation

### 3.1 Input file

`data/imports/pelm_monthly.csv` — three columns, hand-maintained:

    month_end_date,value_gbp,external_flow_gbp
    2023-09-29,683050.47,
    2023-10-31,678057.01,4774.78
    ...
    2025-05-30,555488.02,-157000.00

Convert the 33 existing rows from the xlsx once; thereafter append ~3 rows per quarter.
Sign convention matches `monthly_inflows_gbp`: positive in, negative out.

> Deliberately skipped: an xlsx ingest script and a ledger PDF parser. Three rows a quarter
> is under a minute of typing, and the flow column has to be read off a PDF by hand
> regardless. Revisit if the file layout survives two quarters unchanged.

### 3.2 dbt

- Load `pelm_monthly.csv` as a **dbt seed** — the same mechanism already used for
  `dim_date`, no new code path, and it keeps the file version-controlled alongside the
  models.
- `base__pelm_valuations` — typed view over the seed (dates cast, columns renamed),
  consistent with the existing base layer convention.
- `dim_account` — add a third row `PELM`, `account_open_date = 2023-09-29`, plus a new
  `data_grain` column (`'daily'` for ISA/SIPP, `'monthly'` for PELM) that the API uses to
  decide which endpoints can serve an account.
- `mart_portfolio_snapshot_monthly` — add a CTE unioning PELM rows into the existing
  output, mapping `value_gbp` to `month_end_value_gbp` and `external_flow_gbp` to
  `monthly_inflows_gbp`. `monthly_net_fund_purchases_gbp` is null for PELM.
- `mart_portfolio_value_daily`, `mart_holdings_latest`, `mart_fund_*` — unchanged, HL-only.
  PELM simply has no rows.
- `mart_portfolio_returns_monthly` and `mart_benchmarks_monthly` — **no changes required**;
  they pick PELM up automatically once the snapshot has rows.

### 3.3 Backend

- `backend/app/routers/portfolio.py` — five signatures use
  `Optional[Literal["ISA", "SIPP"]]`; widen to include `"PELM"`.
- `/portfolio/holdings`, `/portfolio/allocation` and the daily value series join
  `fct_holdings_daily`, which is empty for PELM. Read `data_grain` from `dim_account` and
  return an explicit "not available at this grain" response rather than a silently empty
  chart.
- `/portfolio/contributions` hardcodes ISA/SIPP columns (`portfolio.py:150`). Leave PELM
  out — it is a trust, not a contribution account, and has no UK tax-year contribution
  story.
- Returns, Sharpe and benchmark endpoints need no query changes beyond the Literal
  widening.

### 3.4 Frontend

- **Shows PELM:** Overview, Benchmarks, returns/Sharpe comparisons.
- **Excludes PELM:** Holdings, Transactions, Fund Performance, FY Contributions.
- The Overview value chart is daily for ISA/SIPP and monthly for PELM — render PELM as a
  monthly step/point series rather than interpolating a daily line it doesn't have.

### 3.5 Validation

One check, asserting the chain-linked TWR over the full seed reproduces the figure agreed
with B&C (currently 23.4%, pending §6 question 1). It catches the three realistic failure
modes of a hand-maintained file: a flipped flow sign, a missed withdrawal, and a duplicated
month.

---

## 4. Quarterly update process

1. Quarterly email arrives from Barratt & Cooke.
2. Save attachments into `pelm-inputs/`.
3. Append the new month rows to `data/imports/pelm_monthly.csv`, adding any withdrawal or
   transfer read off the ledger.
4. `dbt seed --profiles-dir .` then `dbt run --profiles-dir .`

Not wired into the nightly cron — PELM is manual by nature, and the cron job should skip it
rather than fail nightly on unchanged data.

---

## 5. Explicitly out of scope

| Not doing | Why | Revisit when |
|---|---|---|
| Security-level PELM holdings | No valued position data exists in the source | B&C can supply a machine-readable position file |
| Parsing the costs/charges PDFs | Modified Dietz over net valuations already has fees baked in; extracting them buys only a fee-attribution view | A fee comparison vs HL is explicitly wanted |
| Ledger PDF parser | Two hand-entered flows in three years | Flow frequency rises materially |
| PELM in the nightly cron | Source updates quarterly, by email, by hand | Never, realistically |

---

## 6. Open questions for Barratt & Cooke

Worth one email before building, as question 1 changes what the numbers mean.

1. **Do the month-end valuations include accrued and uninvested income, or is income swept
   to a separate deposit account?** This is the 18.8% vs 23.4% gap, and it decides whether
   PELM's return is comparable like-for-like with the ISA and SIPP figures. If income is
   swept out, we need either total-return valuations or the income ledger.
2. **Please could we have the ledger for the deposit account** — 16 transfers went into it
   over the period and we have no visibility of what happened there.
3. **Please continue to send the valuations file quarterly in this same two-column format**
   — it is the one artefact that matters here, and the format as supplied is ideal.
