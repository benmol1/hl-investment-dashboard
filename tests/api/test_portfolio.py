import pytest


def test_portfolio_value_default(client):
    r = client.get("/portfolio/value")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["date"] == "2024-01-31"
    assert data[0]["value_gbp"] == 15000.0  # ISA 10000 + SIPP 5000


def test_portfolio_value_account_filter(client):
    r = client.get("/portfolio/value?account=ISA")
    assert r.status_code == 200
    data = r.json()
    assert all(row["value_gbp"] in (10000.0, 10500.0) for row in data)


def test_portfolio_value_date_range(client):
    r = client.get("/portfolio/value?from=2024-02-01&to=2024-02-29")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["date"] == "2024-02-29"


def test_portfolio_allocation_default(client):
    r = client.get("/portfolio/allocation")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    item = data[0]
    assert "fund_id" in item
    assert "percentage" in item
    assert item["percentage"] == 100.0  # only one fund in seed across both accounts


def test_portfolio_allocation_account_filter(client):
    r = client.get("/portfolio/allocation?account=SIPP")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["fund_id"] == "FUND_A"


def test_inflows(client):
    r = client.get("/portfolio/inflows")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert "cumulative_inflows" in data[0]
    assert "growth" in data[0]


def test_contributions_financial_year(client):
    r = client.get("/portfolio/contributions/financial-year")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    first = data[0]
    assert first["financial_year"] == "2023/24"
    assert first["isa_gbp"] == 5000.0
    assert first["sipp_gbp"] == 3000.0
    assert first["total_gbp"] == 8000.0


def test_performance_default(client):
    r = client.get("/portfolio/performance?from=2024-01-01&to=2024-02-29")
    assert r.status_code == 200
    data = r.json()
    assert "portfolio" in data
    assert "FTSE100" in data
    assert "SP500" in data
    assert "NASDAQ" in data
    assert "sharpe" in data
    assert "portfolio" in data["sharpe"]
    portfolio_series = data["portfolio"]
    assert len(portfolio_series) == 2
    assert portfolio_series[0]["indexed"] == 100.0


def test_holdings_default(client):
    r = client.get("/portfolio/holdings")
    assert r.status_code == 200
    data = r.json()
    types = {item["holding_type"] for item in data}
    assert "fund" in types
    assert "cash" in types


def test_holdings_account_filter(client):
    r = client.get("/portfolio/holdings?account=ISA")
    assert r.status_code == 200
    data = r.json()
    fund_items = [x for x in data if x["holding_type"] == "fund"]
    cash_items = [x for x in data if x["holding_type"] == "cash"]
    assert len(fund_items) == 1
    assert fund_items[0]["fund_id"] == "FUND_A"
    assert len(cash_items) == 1
    assert "ISA" in cash_items[0]["fund_name"]


def test_freshness(client):
    r = client.get("/portfolio/freshness")
    assert r.status_code == 200
    data = r.json()
    assert "transaction_date" in data
    assert "price_date" in data
    assert data["transaction_date"] is not None
    assert data["price_date"] is not None


def test_ingest_log(client, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.routers.portfolio.PELM_DIR", tmp_path
    )  # no PELM files here
    r = client.get("/portfolio/ingest-log")
    assert r.status_code == 200
    data = r.json()
    hl = [e for e in data if not e["source"].startswith("pelm_")]
    assert {entry["source"] for entry in hl} == {"transactions", "prices"}
    for entry in hl:
        assert "latest_data_date" in entry
        assert "last_successful_at" in entry


def test_ingest_log_includes_pelm_rows(client, tmp_path, monkeypatch):
    for name in (
        "pelm_transactions.csv",
        "pelm_monthly.csv",
        "pelm_ledger_coverage.csv",
    ):
        (tmp_path / name).write_text("x\n")
    monkeypatch.setattr("app.routers.portfolio.PELM_DIR", tmp_path)
    by_source = {e["source"]: e for e in client.get("/portfolio/ingest-log").json()}
    # Latest data dates come from the data; run times are the files' modified times.
    assert by_source["pelm_transactions"]["latest_data_date"] == "2024-02-02"
    assert by_source["pelm_valuations"]["latest_data_date"] == "2024-02-29"
    assert by_source["pelm_income_ledgers"]["latest_data_date"] == "2024-03-31"
    for source in ("pelm_transactions", "pelm_valuations", "pelm_income_ledgers"):
        assert by_source[source]["last_successful_at"] is not None
        assert by_source[source]["last_rows_imported_at"] is not None


def test_ingest_log_pelm_rows_without_files(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.routers.portfolio.PELM_DIR", tmp_path)
    by_source = {e["source"]: e for e in client.get("/portfolio/ingest-log").json()}
    assert by_source["pelm_valuations"]["latest_data_date"] == "2024-02-29"
    assert by_source["pelm_valuations"]["last_successful_at"] is None


# --- PELM (monthly-grain account) -------------------------------------------


def test_value_pelm_returns_monthly_points(client):
    r = client.get("/portfolio/value?account=PELM")
    assert r.status_code == 200
    data = r.json()
    # One point per valuation; the NULL month is dropped, nothing interpolated.
    assert [p["value_gbp"] for p in data] == [1000.0, 1050.0, 1155.0]


def test_value_default_excludes_pelm(client):
    r = client.get("/portfolio/value")
    assert {p["value_gbp"] for p in r.json()} == {15000.0, 15700.0}


@pytest.mark.parametrize(
    "path",
    [
        "/portfolio/holdings?account=PELM",
        "/portfolio/allocation?account=PELM",
        "/portfolio/inflows?account=PELM",
    ],
)
def test_daily_only_endpoints_reject_pelm(client, path):
    r = client.get(path)
    assert r.status_code == 400
    assert "PELM" in r.json()["detail"]


def test_performance_pelm_benchmarks_share_its_dates(client):
    r = client.get("/portfolio/performance?account=PELM")
    assert r.status_code == 200
    data = r.json()
    assert data["start_date"] == "2024-01-31"
    assert [p["indexed"] for p in data["portfolio"]] == [100.0, 110.0]
    # PELM sits on the same calendar month-ends as the benchmarks.
    assert [p["date"] for p in data["FTSE100"]] == [
        p["date"] for p in data["portfolio"]
    ]
    # PELM's own latest Sharpe row, not the latest row across all accounts.
    assert data["sharpe"]["portfolio"]["trailing_12m"] == 0.9


def test_performance_default_excludes_pelm(client):
    r = client.get("/portfolio/performance")
    data = r.json()
    # ISA + SIPP only: PELM's 10% month would otherwise lift the blended index.
    assert data["portfolio"][-1]["indexed"] < 103


def test_performance_pelm_lists_months_with_incomplete_flows(client):
    data = client.get("/portfolio/performance?account=PELM").json()
    assert data["incomplete_flow_dates"] == ["2024-02-29"]


def test_performance_hl_accounts_have_complete_flows(client):
    assert client.get("/portfolio/performance").json()["incomplete_flow_dates"] == []


def test_performance_estimate_lifts_only_incomplete_months(client):
    actual = client.get("/portfolio/performance?account=PELM").json()["portfolio"]
    est = client.get("/portfolio/performance?account=PELM&estimate=true").json()[
        "portfolio"
    ]
    assert actual[-1]["indexed"] == 110.0
    assert est[-1]["indexed"] == 111.0  # Feb is incomplete: 10% + 1% uplift


def test_performance_estimate_leaves_hl_accounts_unchanged(client):
    a = client.get("/portfolio/performance").json()["portfolio"]
    b = client.get("/portfolio/performance?estimate=true").json()["portfolio"]
    assert a == b


def test_quarterly_returns_link_months_and_match_benchmark_months(client):
    [q] = client.get("/portfolio/returns/quarterly?account=PELM").json()["quarters"]
    # Jan is the anchor month; only Feb's return falls in the window, so Q1 is partial.
    assert q["quarter"] == "2024-Q1"
    assert q["months"] == 1
    assert q["start_date"] == "2024-01-31" and q["end_date"] == "2024-02-29"
    assert round(q["portfolio"], 6) == 0.10
    assert round(q["FTSE100"], 6) == round(7600 / 7500 - 1, 6)
    assert q["flows_complete"] is False and q["estimated"] is False


def test_quarterly_returns_estimate_flag(client):
    [q] = client.get("/portfolio/returns/quarterly?account=PELM&estimate=true").json()[
        "quarters"
    ]
    assert round(q["portfolio"], 6) == 0.11
    assert q["estimated"] is True


def test_quarterly_returns_default_is_isa_plus_sipp(client):
    [q] = client.get("/portfolio/returns/quarterly").json()["quarters"]
    assert q["flows_complete"] is True
    # BMV-weighted Feb: (0.02*10050 + 0.01*5025) / 15075
    assert round(q["portfolio"], 6) == round((0.02 * 10050 + 0.01 * 5025) / 15075, 6)
