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


def test_ingest_log(client):
    r = client.get("/portfolio/ingest-log")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    sources = {entry["source"] for entry in data}
    assert sources == {"transactions", "prices"}
    for entry in data:
        assert "latest_data_date" in entry
        assert "last_successful_at" in entry
