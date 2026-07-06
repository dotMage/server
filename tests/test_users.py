"""Team-of-one user model tests (spec E.9, Phase 2 — invisible release)."""

from sqlalchemy import select, text

from src.core.db.migrate import ensure_owner_user
from src.models.base import Account, Device, User


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _session():
    from tests.conftest import _Session

    return _Session()


def test_init_creates_owner_user(bootstrapped_client):
    client, token, _ = bootstrapped_client
    with _session() as s:
        users = list(s.execute(select(User)).scalars())
        assert len(users) == 1
        owner = users[0]
        assert owner.role == "owner"
        assert owner.name == "owner"
        assert owner.key_gen == 1
        account = s.execute(select(Account)).scalar_one()
        assert owner.wrapped_ak == account.wrapped_ak
        device = s.execute(select(Device)).scalar_one()
        assert device.user_id == owner.id


def test_whoami(bootstrapped_client):
    client, token, _ = bootstrapped_client
    r = client.get("/api/v1/whoami", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "owner"
    assert body["role"] == "owner"
    assert body["user_id"] is not None
    assert body["device_name"] == "test-device"


def test_migration_backfills_owner_for_legacy_account(bootstrapped_client):
    """Simulate a pre-team DB: drop the user rows, run the migration."""
    client, token, _ = bootstrapped_client
    with _session() as s:
        s.execute(text("UPDATE devices SET user_id = NULL"))
        s.execute(text("DELETE FROM users"))
        s.commit()

        ensure_owner_user(s)

        owner = s.execute(select(User)).scalar_one()
        assert owner.role == "owner"
        account = s.execute(select(Account)).scalar_one()
        assert owner.wrapped_ak == account.wrapped_ak
        assert owner.key_gen == account.current_key_gen
        device = s.execute(select(Device)).scalar_one()
        assert device.user_id == owner.id

        # idempotent
        ensure_owner_user(s)
        assert len(list(s.execute(select(User)).scalars())) == 1

    # keys endpoint still serves the same wrap
    keys = client.get("/api/v1/account/keys", headers=_auth(token)).json()
    assert keys["wrapped_ak"] == "dGVzdHdyYXBwZWRhazEyMzQ1Njc4OTAxMjM0NTY="


def test_patch_keys_dual_writes_user_row(bootstrapped_client):
    client, token, _ = bootstrapped_client
    r = client.patch(
        "/api/v1/account/keys",
        json={"nonce_ak": "bmV3bm9uY2U=", "wrapped_ak": "bmV3d3JhcA==", "salt": None},
        headers=_auth(token),
    )
    assert r.status_code == 200
    with _session() as s:
        owner = s.execute(select(User)).scalar_one()
        assert owner.wrapped_ak == "bmV3d3JhcA=="
        account = s.execute(select(Account)).scalar_one()
        assert account.wrapped_ak == "bmV3d3JhcA=="


def test_rotation_cuts_over_user_row(bootstrapped_client):
    client, token, _ = bootstrapped_client
    client.post("/api/v1/apps", json={"name": "a"}, headers=_auth(token))
    client.post("/api/v1/apps/a/envs", json={"name": "dev"}, headers=_auth(token))
    client.post(
        "/api/v1/apps/a/envs/dev/revisions",
        json={"blob": "v1:eA==:eQ==", "content_hash": None, "parent_rev": 0},
        headers=_auth(token),
    )
    client.post(
        "/api/v1/account/rotate/begin",
        json={"new_key_gen": 2, "nonce_ak": "bjI=", "wrapped_ak": "dzI="},
        headers=_auth(token),
    )
    client.put(
        "/api/v1/apps/a/envs/dev/revisions/1/blob",
        json={"blob": "v1:bjI=:YzI=", "key_gen": 2},
        headers=_auth(token),
    )
    r = client.post("/api/v1/account/rotate/complete", headers=_auth(token))
    assert r.status_code == 200
    with _session() as s:
        owner = s.execute(select(User)).scalar_one()
        assert owner.key_gen == 2
        assert owner.wrapped_ak == "dzI="


def test_health_features_solo_vs_team(bootstrapped_client, monkeypatch):
    client, token, _ = bootstrapped_client
    assert client.get("/health").json()["features"] == ["rotation"]

    from src.settings import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "MODE", "team")
    assert client.get("/health").json()["features"] == ["rotation", "team"]


def test_enrolled_device_inherits_issuer_user(bootstrapped_client):
    client, token, _ = bootstrapped_client
    r = client.post(
        "/api/v1/devices/enroll-token",
        json={"name": "second", "ttl": "1h"},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    enroll_token = r.json()["token"]
    r = client.post(
        "/api/v1/auth/device",
        json={"device_name": "second-laptop"},
        headers={"Authorization": f"Bearer {enroll_token}"},
    )
    assert r.status_code in (200, 201), r.text
    with _session() as s:
        owner = s.execute(select(User)).scalar_one()
        second = s.execute(
            select(Device).where(Device.name == "second-laptop")
        ).scalar_one()
        assert second.user_id == owner.id


def test_migration_is_noop_with_multiple_users(bootstrapped_client):
    """Regression: startup migration must not crash on a team account."""
    from src.models.base import User

    client, token, _ = bootstrapped_client
    with _session() as s:
        account_id = s.execute(select(Account)).scalar_one().id
        s.add(
            User(
                account_id=account_id,
                name="second",
                role="editor",
                salt="cw==",
                nonce_ak="bg==",
                wrapped_ak="dw==",
            )
        )
        s.commit()
        ensure_owner_user(s)  # must not raise
        assert len(list(s.execute(select(User)).scalars())) == 2


def test_web_enroll_token_keeps_inviter_identity(bootstrapped_client, monkeypatch):
    """A token minted by a member enrolls a device under THAT member, not owner
    (regression: web admin showed 'owner' for a token minted by an editor)."""
    from src.settings import get_settings
    from src.models.base import User
    monkeypatch.setattr(get_settings(), "MODE", "team")
    client, owner_token, _ = bootstrapped_client

    # owner invites + editor joins
    import hashlib
    inv = client.post("/api/v1/users/invite", json={
        "name": "vsky", "role": "editor", "ttl": "24h",
        "sealed_ak": "c2VhbGVk", "nonce_inv": "bg==",
        "redeem_hash": hashlib.sha256(b"s").hexdigest(),
    }, headers=_auth(owner_token)).json()
    joined = client.post("/api/v1/invitations/complete", json={
        "invitation_id": inv["invitation_id"], "redeem_secret": "s",
        "device_name": "vsky-laptop", "salt": "a2s=", "argon_memory": 65536,
        "argon_iterations": 3, "argon_parallelism": 1, "argon_version": 19,
        "nonce_ak": "bg==", "wrapped_ak": "dw==",
    }).json()
    vsky_token = joined["device_token"]

    # vsky mints a web-admin enrollment token, web exchanges it
    et = client.post("/api/v1/devices/enroll-token",
                     json={"name": "web-admin", "ttl": "5m"},
                     headers=_auth(vsky_token)).json()["token"]
    web = client.post("/api/v1/auth/device", json={"device_name": "web-admin"},
                      headers={"Authorization": f"Bearer {et}"}).json()

    me = client.get("/api/v1/whoami", headers=_auth(web["device_token"])).json()
    assert me["name"] == "vsky"
    assert me["role"] == "editor"
