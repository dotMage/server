"""Health endpoint tests."""


def test_health_no_account(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["account_exists"] is False


def test_health_with_account(bootstrapped_client):
    client, _, _ = bootstrapped_client
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["account_exists"] is True
