def test_pelm_transactions_hides_internal_transfers_by_default(client):
    r = client.get("/pelm/transactions")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 4
    assert {i["tx_type"] for i in data["items"]} == {
        "BUY",
        "SELL",
        "WITHDRAWAL",
        "STOCK_TRANSFER_IN",
    }


def test_pelm_transactions_include_internal(client):
    r = client.get("/pelm/transactions?include_internal=true")
    assert r.json()["total"] == 5
    assert "DEPOSIT_TRANSFER_OUT" in {i["tx_type"] for i in r.json()["items"]}


def test_pelm_transactions_most_recent_first(client):
    dates = [i["tx_date"] for i in client.get("/pelm/transactions").json()["items"]]
    assert dates == sorted(dates, reverse=True)


def test_pelm_transactions_filters(client):
    r = client.get("/pelm/transactions?type=sell")
    assert [i["security"] for i in r.json()["items"]] == ["ACME PLC"]
    r = client.get("/pelm/transactions?from=2024-02-01")
    assert r.json()["total"] == 2


def test_pelm_transactions_keep_null_amounts(client):
    items = client.get("/pelm/transactions?type=STOCK_TRANSFER_IN").json()["items"]
    assert items[0]["amount_gbp"] is None
    assert items[0]["quantity"] == 50.0


def test_pelm_transactions_pagination(client):
    r = client.get("/pelm/transactions?per_page=3&page=2")
    data = r.json()
    assert data["total"] == 4 and len(data["items"]) == 1


def test_pelm_composition_only_months_with_a_cash_balance(client):
    data = client.get("/pelm/composition").json()
    assert [(p["date"], p["cash_gbp"], p["invested_gbp"]) for p in data] == [
        ("2024-01-31", 200.0, 850.0),
        ("2024-02-29", 300.0, 855.0),
    ]


def test_pelm_transactions_carry_their_ledger(client):
    items = client.get("/pelm/transactions").json()["items"]
    assert {i["ledger"] for i in items} == {"capital"}


def test_pelm_transactions_category_filter(client):
    r = client.get("/pelm/transactions?category=external_flow")
    assert {i["tx_type"] for i in r.json()["items"]} == {
        "WITHDRAWAL",
        "STOCK_TRANSFER_IN",
    }


def test_pelm_income_by_quarter_only_periods_with_income_ledgers(client):
    data = client.get("/pelm/income").json()
    # 2023-Q4 and 2024-Q2 have no complete month, so they are left out.
    assert [p["period"] for p in data["periods"]] == ["2024-Q1"]
    q1 = data["periods"][0]
    assert q1["period_start"] == "2024-01-01" and q1["period_end"] == "2024-03-31"
    assert q1["dividends_gbp"] == 60.0 and q1["income_gbp"] == 63.0
    assert q1["custody_fees_gbp"] == 90.0 and q1["income_distributed_gbp"] == 52.0
    assert q1["income_complete"] is True
    assert q1["fees_complete"] is False  # only January had a fees ledger
    assert data["trailing_12m_income_gbp"] is None


def test_pelm_income_by_month(client):
    data = client.get("/pelm/income?grain=month").json()
    assert [p["period"] for p in data["periods"]] == ["2024-01", "2024-02", "2024-03"]
    assert data["periods"][0]["period_start"] == "2024-01-01"
    assert data["periods"][0]["fees_complete"] is True


def test_pelm_reconciliation(client):
    rows = client.get("/pelm/reconciliation").json()
    assert rows == [
        {
            "period_start": "2024-01-01",
            "period_end": "2024-03-31",
            "source": "Report to 31.3.24",
            "reported_return": 0.0448,
            "dashboard_return": 0.0450,
            "difference_pp": 0.02,
            "net_outflows_gbp": 52.0,
            "coverage": "Complete",
        }
    ]
