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
