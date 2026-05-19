def test_transactions_default(client):
    r = client.get("/transactions")
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert "items" in data
    assert data["total"] == 3
    assert len(data["items"]) == 3


def test_transactions_pagination(client):
    r = client.get("/transactions?per_page=1&page=1")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert len(data["items"]) == 1
    assert data["page"] == 1
    assert data["per_page"] == 1


def test_transactions_pagination_second_page(client):
    r = client.get("/transactions?per_page=2&page=2")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert len(data["items"]) == 1


def test_transactions_account_filter(client):
    r = client.get("/transactions?account=ISA")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert all(item["account_id"] == "ISA" for item in data["items"])


def test_transactions_type_filter(client):
    r = client.get("/transactions?type=BUY")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["transaction_type"] == "BUY"


def test_transactions_date_range(client):
    r = client.get("/transactions?from=2024-02-01&to=2024-02-29")
    assert r.status_code == 200
    data = r.json()
    # Only TX003 has trade_date_key=2 (2024-02-29)
    assert data["total"] == 1


def test_transactions_invalid_type_ignored(client):
    # Invalid type is silently ignored — all results returned
    r = client.get("/transactions?type=BOGUS")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
