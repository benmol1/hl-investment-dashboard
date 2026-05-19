import pytest


def test_list_funds_all(client):
    r = client.get("/funds")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    ids = {f["id"] for f in data}
    assert ids == {"FUND_A", "FUND_B"}


def test_list_funds_active_only(client):
    r = client.get("/funds?active_only=true")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["id"] == "FUND_A"
    assert data[0]["is_active"] is True


def test_fund_performance(client):
    r = client.get("/funds/FUND_A/performance?from=2024-01-01&to=2024-02-29")
    assert r.status_code == 200
    data = r.json()
    assert data["fund_id"] == "FUND_A"
    assert len(data["fund"]) == 2
    assert data["fund"][0]["indexed"] == 100.0
    assert data["fund"][1]["indexed"] == pytest.approx(104.0, rel=1e-3)
    assert len(data["FTSE100"]) == 2
    assert data["FTSE100"][0]["indexed"] == 100.0


def test_fund_performance_not_found(client):
    r = client.get("/funds/NONEXISTENT/performance")
    assert r.status_code == 404
