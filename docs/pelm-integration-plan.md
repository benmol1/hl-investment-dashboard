# PELM Will Trust — Design and As-Built Notes

*Drafted 2026-09-11 · Implemented on `feature/pelm-will-trust` (PR #24) · Updated 2026-11-23 to describe what was actually built*

Adds the **P E L Molyneaux Will Trust** (account `C070982`, managed by Barratt & Cooke) to the
dashboard as a third account alongside the HL ISA and SIPP, so its performance can be compared
against both and against the existing benchmarks.

**The trust is not the owner's money.** It is therefore never included in any total or average:
the default view everywhere is ISA + SIPP, and PELM appears only when selected explicitly.

To-do list: [pelm-todo.md](pelm-todo.md) · Update steps: README, "Updating PELM Will Trust data".

---

## 1. Source material

Supplied by Barratt & Cooke on 4 June 2026, extracted into `pelm-inputs/` (gitignored — only its
README is tracked).

| File | Content | Used? |
|---|---|---|
| `C070982 End of Month Valuations.xlsx` | 33 rows: month-end date + total market value, Sep 2023 → May 2026 | Yes — typed into `pelm_monthly.csv` |
| `C070982 Ledger statements.pdf` | 3 pages, GIA cash ledger 4 Sep 2023 – 4 Jun 2026: buys/sells, transfers in/out, one BACS payment | Yes — parsed into `pelm_transactions.csv` |
| `C070982 Breakdown 2023-2024 … 2026.pdf` | Per-transaction commission / stamp duty / PTM levy, plus fund OCF rates | No — kept for reference |

### Findings that drove the design

**1. The portfolio is a single number, not a holdings list.** The valuations file carries no
per-security breakdown, and the ledger records the inception in-specie transfers as bare
quantities (`13500 THE RENEWABLES INFR`) with **no value attached**. Daily security-level
holdings cannot be reconstructed from this data.

**2. There are material external cash flows that must not be read as performance.** The £140k
fall between Apr and May 2025 is a `BACS Payment *3850` of **£157,000** on 21 May 2025.
Inception also brought in £20,679.81 (21 Sep 2023, inside the opening valuation) and £4,774.78
(24 Oct 2023). Treating the valuation series naively as a return series gives **−7.0%**;
chain-linking with these flows gives **+18.8%**.

**3. The ledger is incomplete — it contains no dividends and no fees**, alongside 22 transfers to
and from a deposit account whose ledger we were not sent. Our chain-linked 18.8% sits ~4.6pp below
Alastair's stated total return of **23.4%** for 4 Sep 2023 – 4 Jun 2026. The most likely
explanation is income swept to the deposit account and excluded from the month-end valuations.
This is unresolved (§6, question 1) and should be settled before the comparison against ISA/SIPP
is published anywhere. *(Partly offsetting: our series runs 29 Sep 2023 – 29 May 2026, a slightly
shorter window than theirs.)*

**4. The ledger PDF is machine-readable after all.** The original plan assumed it had to be read
by hand because plain text extraction shuffles the debit and credit columns. Read by word
position, debit amounts sit under one column header and credits under another, and the result
reconciles to the penny: opening 0.00 + credits £817,243.38 − debits £817,243.38 = closing 0.00.

---

## 2. Approach

Two independent pieces, both small and both optional:

**A. A monthly valuation series**, attached at the monthly-snapshot seam.
`mart_portfolio_returns_monthly` reads exactly four fields from `mart_portfolio_snapshot_monthly`
(`account_name`, `year_month`, `month_end_value_gbp`, `monthly_inflows_gbp`). Modified Dietz,
trailing 12m/36m returns, Sharpe ratios and the benchmark comparison all hang off those and
nothing lower. PELM supplies them directly, so it is unioned into the snapshot mart and everything
above picks it up unchanged. There are no PELM holdings, prices or funds.

**B. A ledger view** of trades and cash movements, kept entirely separate from HL's
`fct_transactions` (which is shaped around fund trades, units and prices).

    pelm_monthly.csv (hand-maintained) --> base__pelm_valuations --+
                                                                   |
    fct_holdings_daily + fct_transactions ------------------------>+--> mart_portfolio_snapshot_monthly
                                                                   |         |
                                                                   |         v
                                                                   |   returns / benchmarks / overview
                                                                   |
    Ledger PDF --parse_pelm_ledger.py--> pelm_transactions.csv --> base__pelm_transactions
                                                                         |
                                                                         v
                                                                  fct_pelm_transactions --> /pelm/transactions

### Why not model PELM properly?

Reconstructing daily holdings would mean inventing valuations for the in-specie transfers,
sourcing daily prices for ~40 individual equities across four currencies, and maintaining all of
it quarterly — to arrive at the same monthly return series the spreadsheet already gives us.

---

## 3. What was built

### 3.1 Input files — `data/pelm/` (gitignored CSVs)

| File | Source | Columns |
|---|---|---|
| `pelm_monthly.csv` | Typed by hand from the valuations xlsx | `month_end_date, value_gbp, external_flow_gbp` |
| `pelm_transactions.csv` | Generated by the ledger parser | `tx_date, reference, tx_type, security, quantity, amount_gbp, notes` |

`external_flow_gbp` is positive for money in, negative for money out, blank if none. In
`pelm_monthly.csv` the real flows are `+4774.78` (Oct 2023) and `-157000.00` (May 2025). Example
layouts are in `data/examples/`.

**Why `data/` and not a dbt seed.** The first design used a dbt seed. But the cron image bakes
`dbt/` in at build time and the file is personal data, so a gitignored seed would be missing on
the server and break the nightly `dbt build`, and need an image rebuild each quarter. Reading the
files from the bind-mounted `data/` folder avoids both.

### 3.2 dbt

- **Macros** (`dbt/macros/pelm_monthly_source.sql`): `pelm_read_csv` reads a file with explicit
  column types, or returns an empty result with the same columns if it does not exist.
  `pelm_monthly_source` and `pelm_transactions_source` wrap it. Paths are relative to the dbt
  project directory (`../data/pelm/…`) and can be overridden with `--vars`. Result: `dbt build`
  passes with the files present or absent.
- **`base__pelm_valuations`** (a table, not a view, because its source is a relative path). Maps
  Barratt & Cooke's last-working-day dates onto **calendar month-ends**, matching `dim_date` and
  the benchmark series, so PELM lines up with everything else with no special cases. The supplied
  date is kept as `valuation_date`. A day or two is immaterial for a long-term series.
- **`dim_account`**: new `data_grain` column (`daily` for ISA/SIPP, `monthly` for PELM). The PELM
  row is derived from the valuations, so no file means no PELM row.
- **`mart_portfolio_snapshot_monthly`**: unions PELM month-end values and external flows.
  `monthly_net_fund_purchases_gbp` is null for PELM. PELM's month spine stops at its last
  valuation month instead of running to today.
- **`int_cash_values_daily`**: now filtered to `data_grain = 'daily'`, otherwise PELM would get a
  daily cash spine of zeros.
- **`base__pelm_transactions`** and **`fct_pelm_transactions`**: the ledger lines with a
  `category` — `trade`, `external_flow`, `internal_transfer` (deposit sweeps),
  `corporate_action` (including cash fractions), `other`.
- Unchanged and HL-only: `mart_portfolio_value_daily`, `mart_holdings_latest`, `mart_fund_*`.
  `mart_portfolio_returns_monthly` and `mart_benchmarks_monthly` needed no changes.
- Tests: unique and not-null on the PELM months, accepted-value tests on `tx_type`, `category` and
  `data_grain`.

### 3.3 Ledger parser — `backend/scripts/parse_pelm_ledger.py`

Reads the ledger PDF by word position (`pdfplumber`) into `pelm_transactions.csv`.

- **Refuses to write unless the ledger balances** (opening + credits − debits = closing).
- Classifies each line: `BUY`, `SELL`, `CASH_TRANSFER_IN`, `WITHDRAWAL`, `DEPOSIT_TRANSFER_IN` /
  `DEPOSIT_TRANSFER_OUT`, `STOCK_TRANSFER_IN` (one row per security), `CORPORATE_ACTION`,
  `CASH_FRACTION`, `OTHER`. 103 ledger entries become 132 rows. Foreign-currency trades keep their
  FX rate in `notes`.
- **Compares the ledger's external flows with the `external_flow_gbp` column** of
  `pelm_monthly.csv` and reports any difference. They currently agree.
- With no arguments it finds the PDF in `pelm-inputs/` (laptop) or `data/pelm/` (server).
  `pdfplumber` is a main dependency so it also runs inside the cron container.
- One entry stays `OTHER`: a £108 "to settlement" on 26 Sep 2023 whose meaning is unknown.

### 3.4 Backend

- **`/portfolio/*`** accepts `PELM` as an account.
  - `/portfolio/holdings`, `/allocation` and `/inflows` return a 400 for monthly-grain accounts
    ("only has month-end valuations") rather than a silently empty chart.
  - `/portfolio/value?account=PELM` returns the month-end points as they are, with no interpolation.
  - `/portfolio/performance`: with **no account selected it aggregates ISA + SIPP only**; PELM is
    compared by selecting it. For PELM the benchmarks stop at its last valuation, and its Sharpe
    ratios come from its own latest row (not the latest across all accounts).
  - `/portfolio/contributions/financial-year` leaves PELM out: a trust has no tax-year
    contribution story.
- **`/pelm/transactions`** (new): paginated ledger lines, most recent first, with `type`, `from`,
  `to` filters. Deposit-account sweeps are hidden unless `include_internal=true`.
- **`/portfolio/ingest-log`** gains two rows, PELM transactions and PELM month-end positions. PELM
  is manual, so their run times are the source files' modified times, and the latest data date
  comes from the data.
- `/transactions` is unchanged (ISA / SIPP only).
- **Telegram:** the monthly summary in `cron.py` covers daily-grain accounts only. The bot's named
  tools still cover ISA and SIPP; PELM is reachable through `query_database` (mart/dim tables only,
  restriction unchanged) and the system prompt mentions it.

### 3.5 Frontend

- **Benchmarks**: any combination of **ISA + SIPP / ISA / SIPP / PELM Trust** can be selected at
  once, and **each of FTSE 100, S&P 500 and Nasdaq** toggled on or off. When accounts began at
  different times, every series is rebased to 100 at the latest start month so they are
  like-for-like (the chart title shows it). PELM defaults to off.
- **Overview**: PELM shows as monthly points with a "month-end valuation as at …" caption, and the
  allocation card is replaced by a note that there is no fund breakdown.
- **Transactions**: a PELM Trust toggle swaps in the ledger view — date, type, security, quantity,
  amount, notes — with a type filter, a "show deposit-account transfers" checkbox, and a note that
  the ledger has no dividends or fees. The first toggle reads "ISA + SIPP" rather than "All".
- **Data Ingestion Log**: the two PELM rows, with a footnote that their times are file-update times.
- **No PELM option** on Holdings, Inflows, Fund Performance or FY Contributions.

### 3.6 Tests

Backend: 62 tests, including PELM value, 400 responses, performance alignment, aggregate
exclusion, `/pelm/transactions`, and ingest-log rows. dbt: all tests pass with the files present
and absent. The browser pages were exercised in Chrome, including every account and benchmark
toggle combination.

### 3.7 Decisions that differ from the original plan

| Original plan | As built | Why |
|---|---|---|
| dbt seed at `data/imports/pelm_monthly.csv` | Macro reading `data/pelm/*.csv` | A gitignored seed would be missing on the Pi and break the nightly build |
| Keep supplied last-working-day dates | Map onto calendar month-ends | Lines up with `dim_date`/benchmarks; removed several workarounds |
| No-account aggregate would include PELM | Aggregate is ISA + SIPP only | PELM is not the owner's money |
| No ledger parser; hand-key the flows | Parser with balance check and flow reconciliation | The PDF is parseable by position and the ledger reconciles exactly |
| Transactions page excludes PELM | Separate PELM ledger view | Requested; kept separate from HL's fund-shaped transaction model |
| Single validation check on the 23.4% return | **Dropped** | The parser's flow reconciliation and the dbt uniqueness/not-null tests cover the same failure modes; the reference figure is still unexplained |
| Benchmarks page: one account at a time | Multi-select accounts and benchmark toggles | Requested |

---

## 4. Quarterly update process

Done on the Pi; nothing needs an image rebuild (after the one-off rebuild that added `pdfplumber`).

1. Copy the Barratt & Cooke attachments into `/srv/hl-dashboard/data/pelm/` (keep the ledger's
   filename, `C070982 Ledger statements.pdf`).
2. Append the new months to `pelm_monthly.csv`, adding any withdrawal or transfer read off the ledger.
3. Run the parser: `docker compose exec cron /app/.venv/bin/python backend/scripts/parse_pelm_ledger.py`.
   Fix anything it reports.
4. `dbt build`, or wait for the 01:00 refresh.

Exact commands are in the README. There is no ingest script for PELM: nothing in the nightly
cron fetches or parses it. The nightly `dbt build` simply re-reads the files, which is harmless.

---

## 5. Explicitly out of scope

| Not doing | Why | Revisit when |
|---|---|---|
| Security-level PELM holdings | No valued position data exists in the source | B&C can supply a machine-readable position file |
| Parsing the costs/charges PDFs | Modified Dietz over net valuations already has fees baked in | A fee comparison vs HL is explicitly wanted |
| An xlsx ingest script | Three rows a quarter is under a minute of typing | The file layout stops being stable |
| PELM-specific nightly cron job | Source updates quarterly, by email, by hand | Never, realistically |
| The total-return validation check | See §3.7 | The 18.8% vs 23.4% gap is explained |

---

## 6. Open questions for Barratt & Cooke

Not yet sent. Question 1 changes what the numbers mean, and should be answered before the PELM
comparison is relied on or published.

1. **Do the month-end valuations include accrued and uninvested income, or is income swept to a
   separate deposit account?** This is the 18.8% vs 23.4% gap, and it decides whether PELM's
   return is comparable like-for-like with the ISA and SIPP figures.
2. **Please could we have the ledger for the deposit account** — 22 transfers went to or from it
   and we have no visibility of what happened there.
3. **Please continue to send the valuations file quarterly in this same two-column format.**

Worth adding to the same email:

- **March 2026** shows a −9.1% month (valuation £649k → £590k) with no flow in the ledger. A market
  fall, or a missing withdrawal?
- **A £108 debit "TO SETTLEMENT" on 26 Sep 2023** — what is it?
