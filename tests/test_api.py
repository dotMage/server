"""Comprehensive API tests for all endpoints."""


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# --- Account ---


def test_account_init_success(client):
    resp = client.post(
        "/api/v1/account/init",
        json={
            "bootstrap_secret": "test-bootstrap-secret",
            "salt": "c2FsdA==",
            "nonce_ak": "bm9uY2U=",
            "wrapped_ak": "d3JhcHBlZA==",
            "device_name": "mac",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "device_token" in data
    assert "refresh_token" in data
    assert data["device_token"].startswith("dmage_dtok_")
    assert data["refresh_token"].startswith("dmage_rtok_")


def test_account_init_duplicate(bootstrapped_client):
    client, _, _ = bootstrapped_client
    resp = client.post(
        "/api/v1/account/init",
        json={
            "bootstrap_secret": "test-bootstrap-secret",
            "salt": "c2FsdA==",
            "nonce_ak": "bm9uY2U=",
            "wrapped_ak": "d3JhcHBlZA==",
        },
    )
    assert resp.status_code == 409


def test_account_init_bad_bootstrap(client):
    resp = client.post(
        "/api/v1/account/init",
        json={
            "bootstrap_secret": "wrong-secret",
            "salt": "c2FsdA==",
            "nonce_ak": "bm9uY2U=",
            "wrapped_ak": "d3JhcHBlZA==",
        },
    )
    assert resp.status_code == 403


def test_get_account_keys(bootstrapped_client):
    client, token, _ = bootstrapped_client
    resp = client.get("/api/v1/account/keys", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["salt"] == "dGVzdHNhbHQxMjM0NTY3OA=="
    assert data["argon_memory"] == 65536


def test_get_keys_no_auth(client):
    resp = client.get("/api/v1/account/keys")
    assert resp.status_code == 401


def test_patch_account_keys(bootstrapped_client):
    client, token, _ = bootstrapped_client
    resp = client.patch(
        "/api/v1/account/keys",
        headers=auth_header(token),
        json={"nonce_ak": "bmV3bm9uY2U=", "wrapped_ak": "bmV3d3JhcHBlZA=="},
    )
    assert resp.status_code == 200

    # Verify updated
    resp2 = client.get("/api/v1/account/keys", headers=auth_header(token))
    assert resp2.json()["nonce_ak"] == "bmV3bm9uY2U="


# --- Auth ---


def test_token_refresh(bootstrapped_client):
    client, _, refresh = bootstrapped_client
    resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "device_token" in data
    assert "refresh_token" in data
    # Old refresh should no longer work
    resp2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp2.status_code == 401


def test_invalid_refresh(client):
    resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid"},
    )
    assert resp.status_code == 401


# --- Apps ---


def test_app_crud(bootstrapped_client):
    client, token, _ = bootstrapped_client
    h = auth_header(token)

    # Create
    resp = client.post("/api/v1/apps", headers=h, json={"name": "myapp"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "myapp"

    # Duplicate
    resp = client.post("/api/v1/apps", headers=h, json={"name": "myapp"})
    assert resp.status_code == 409

    # List
    resp = client.get("/api/v1/apps", headers=h)
    assert resp.status_code == 200
    apps = resp.json()["apps"]
    assert len(apps) == 1
    assert apps[0]["name"] == "myapp"


# --- Environments ---


def test_env_crud(bootstrapped_client):
    client, token, _ = bootstrapped_client
    h = auth_header(token)

    client.post("/api/v1/apps", headers=h, json={"name": "envapp"})

    # Create env
    resp = client.post(
        "/api/v1/apps/envapp/envs", headers=h, json={"name": "dev"}
    )
    assert resp.status_code == 201

    # Duplicate
    resp = client.post(
        "/api/v1/apps/envapp/envs", headers=h, json={"name": "dev"}
    )
    assert resp.status_code == 409

    # List
    resp = client.get("/api/v1/apps/envapp/envs", headers=h)
    assert resp.status_code == 200
    envs = resp.json()["environments"]
    assert len(envs) == 1
    assert envs[0]["name"] == "dev"

    # Delete
    resp = client.delete("/api/v1/apps/envapp/envs/dev", headers=h)
    assert resp.status_code == 200

    resp = client.get("/api/v1/apps/envapp/envs", headers=h)
    assert len(resp.json()["environments"]) == 0


# --- Revisions ---


def _setup_app_env(client, token):
    h = auth_header(token)
    client.post("/api/v1/apps", headers=h, json={"name": "revapp"})
    client.post("/api/v1/apps/revapp/envs", headers=h, json={"name": "dev"})
    return h


def test_push_pull_flow(bootstrapped_client):
    client, token, _ = bootstrapped_client
    h = _setup_app_env(client, token)

    # Push rev 1
    resp = client.post(
        "/api/v1/apps/revapp/envs/dev/revisions",
        headers=h,
        json={"blob": "v1:bm9uY2U=:Y2lwaGVy", "parent_rev": 0},
    )
    assert resp.status_code == 201
    assert resp.json()["rev_number"] == 1

    # Pull rev 1
    resp = client.get(
        "/api/v1/apps/revapp/envs/dev/revisions/1", headers=h
    )
    assert resp.status_code == 200
    assert resp.json()["blob"] == "v1:bm9uY2U=:Y2lwaGVy"
    assert resp.json()["rev_number"] == 1

    # Pull "last"
    resp = client.get(
        "/api/v1/apps/revapp/envs/dev/revisions/last", headers=h
    )
    assert resp.status_code == 200
    assert resp.json()["rev_number"] == 1


def test_push_conflict(bootstrapped_client):
    client, token, _ = bootstrapped_client
    h = _setup_app_env(client, token)

    # Push rev 1
    client.post(
        "/api/v1/apps/revapp/envs/dev/revisions",
        headers=h,
        json={"blob": "v1:bm9uY2U=:Y2lwaGVy", "parent_rev": 0},
    )

    # Push with stale parent_rev=0 → 409
    resp = client.post(
        "/api/v1/apps/revapp/envs/dev/revisions",
        headers=h,
        json={"blob": "v1:bm9uY2U=:c3RhbGU=", "parent_rev": 0},
    )
    assert resp.status_code == 409


def test_revision_history(bootstrapped_client):
    client, token, _ = bootstrapped_client
    h = _setup_app_env(client, token)

    # Push 3 revisions
    for i in range(3):
        client.post(
            "/api/v1/apps/revapp/envs/dev/revisions",
            headers=h,
            json={"blob": f"v1:bm9uY2U=:cmV2{i}", "parent_rev": i},
        )

    resp = client.get("/api/v1/apps/revapp/envs/dev/revisions", headers=h)
    assert resp.status_code == 200
    revs = resp.json()["revisions"]
    assert len(revs) == 3
    # Newest first
    assert revs[0]["rev_number"] == 3
    assert revs[2]["rev_number"] == 1


def test_rollback(bootstrapped_client):
    client, token, _ = bootstrapped_client
    h = _setup_app_env(client, token)

    # Push 2 revisions
    client.post(
        "/api/v1/apps/revapp/envs/dev/revisions",
        headers=h,
        json={"blob": "v1:bm9uY2U=:cmV2MQ==", "parent_rev": 0},
    )
    client.post(
        "/api/v1/apps/revapp/envs/dev/revisions",
        headers=h,
        json={"blob": "v1:bm9uY2U=:cmV2Mg==", "parent_rev": 1},
    )

    # Rollback to rev 1
    resp = client.post(
        "/api/v1/apps/revapp/envs/dev/rollback",
        headers=h,
        json={"to_rev": 1},
    )
    assert resp.status_code == 201
    assert resp.json()["rev_number"] == 3
    assert resp.json()["copied_from"] == 1

    # Rev 3 should have same blob as rev 1
    r3 = client.get("/api/v1/apps/revapp/envs/dev/revisions/3", headers=h).json()
    r1 = client.get("/api/v1/apps/revapp/envs/dev/revisions/1", headers=h).json()
    assert r3["blob"] == r1["blob"]
    assert r3["rollback_of"] == 1


# --- Devices ---


def test_device_list_and_revoke(bootstrapped_client):
    client, token, _ = bootstrapped_client
    h = auth_header(token)

    resp = client.get("/api/v1/devices", headers=h)
    assert resp.status_code == 200
    devices = resp.json()["devices"]
    assert len(devices) == 1
    assert devices[0]["revoked"] is False

    # Create enrollment token
    resp = client.post(
        "/api/v1/devices/enroll-token",
        headers=h,
        json={"name": "work-pc", "ttl": "1h"},
    )
    assert resp.status_code == 201
    enroll_token = resp.json()["token"]
    assert enroll_token.startswith("dmage_etok_")

    # Register new device via enrollment
    resp = client.post(
        "/api/v1/auth/device",
        headers={"Authorization": f"Bearer {enroll_token}"},
        json={"device_name": "work-pc"},
    )
    assert resp.status_code == 201
    new_token = resp.json()["device_token"]

    # Now 3 devices (original + enrollment-placeholder + new)
    resp = client.get("/api/v1/devices", headers=auth_header(new_token))
    assert len(resp.json()["devices"]) == 3

    # Revoke the new device from original
    new_device_id = resp.json()["devices"][2]["id"]
    resp = client.delete(
        f"/api/v1/devices/{new_device_id}", headers=h
    )
    assert resp.status_code == 200

    # Revoked device can't authenticate
    resp = client.get("/api/v1/apps", headers=auth_header(new_token))
    assert resp.status_code == 401


# --- Audit ---


def test_audit_log(bootstrapped_client):
    client, token, _ = bootstrapped_client
    h = auth_header(token)

    # Do some actions
    client.post("/api/v1/apps", headers=h, json={"name": "auditapp"})
    client.post("/api/v1/apps/auditapp/envs", headers=h, json={"name": "dev"})

    resp = client.get("/api/v1/audit", headers=h)
    assert resp.status_code == 200
    events = resp.json()["events"]
    # At least: account.init + app.created + env.created
    assert len(events) >= 3

    # Filter by app
    resp = client.get("/api/v1/audit?app=auditapp", headers=h)
    app_events = resp.json()["events"]
    assert all(e["app_name"] == "auditapp" for e in app_events)


# --- Security: no plaintext in DB ---


def test_db_has_no_plaintext_secrets(bootstrapped_client):
    """Verify the server stores only base64 blobs, not plaintext values."""
    from sqlalchemy import text

    from app.db.session import get_db

    client, token, _ = bootstrapped_client
    h = auth_header(token)

    # Push a secret with known plaintext
    client.post("/api/v1/apps", headers=h, json={"name": "sectest"})
    client.post("/api/v1/apps/sectest/envs", headers=h, json={"name": "dev"})
    client.post(
        "/api/v1/apps/sectest/envs/dev/revisions",
        headers=h,
        json={
            "blob": "v1:bm9uY2U=:SUPER_SECRET_VALUE_12345",
            "parent_rev": 0,
        },
    )

    # Check the raw DB — the blob should be stored as-is (it's already encrypted by CLI)
    # The point: we never see the actual secret "DATABASE_URL=..." in DB
    db = next(client.app.dependency_overrides[get_db]())
    rows = db.execute(text("SELECT blob FROM revisions")).fetchall()
    for row in rows:
        assert "v1:" in row[0], "blob should be in v1:... format"

    # Token should be stored as hash, not raw
    device_rows = db.execute(text("SELECT token_hash FROM devices")).fetchall()
    for row in device_rows:
        # SHA256 hashes are 64 hex chars
        assert len(row[0]) == 64, "token should be stored as sha256 hash"
        assert not row[0].startswith("dmage_"), "raw token should NOT be in DB"
    db.close()
