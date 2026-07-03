"""Invitation flow tests (spec K.1/K.2, team mode)."""

import hashlib

import pytest


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def team_mode(monkeypatch):
    from src.settings import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "MODE", "team")
    yield


def _invite(client, token, name="kolya", role="editor", redeem_secret="rrr", ttl="24h"):
    return client.post(
        "/api/v1/users/invite",
        json={
            "name": name,
            "role": role,
            "ttl": ttl,
            "sealed_ak": "c2VhbGVk",
            "nonce_inv": "bm9uY2VpbnY=",
            "redeem_hash": hashlib.sha256(redeem_secret.encode()).hexdigest(),
        },
        headers=_auth(token),
    )


COMPLETE_KEYS = {
    "device_name": "kolya-laptop",
    "salt": "a29seWFzYWx0MTIzNDU2Nzg=",
    "argon_memory": 65536,
    "argon_iterations": 3,
    "argon_parallelism": 1,
    "argon_version": 19,
    "nonce_ak": "a29seWFub25jZQ==",
    "wrapped_ak": "a29seWF3cmFw",
}


def test_team_endpoints_hidden_in_solo_mode(bootstrapped_client):
    client, token, _ = bootstrapped_client
    assert client.get("/api/v1/users", headers=_auth(token)).status_code == 404
    assert _invite(client, token).status_code == 404
    # whoami is mode-independent
    assert client.get("/api/v1/whoami", headers=_auth(token)).status_code == 200


def test_full_invitation_cycle(bootstrapped_client, team_mode):
    client, token, _ = bootstrapped_client

    r = _invite(client, token)
    assert r.status_code == 201, r.text
    inv_id = r.json()["invitation_id"]

    # pending invitation visible in the list
    listing = client.get("/api/v1/users", headers=_auth(token)).json()
    assert [i["name"] for i in listing["invitations"]] == ["kolya"]

    # step 1: redeem hands out the sealed AK
    r = client.post(
        "/api/v1/invitations/redeem",
        json={"invitation_id": inv_id, "redeem_secret": "rrr"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sealed_ak"] == "c2VhbGVk"
    assert body["nonce_inv"] == "bm9uY2VpbnY="
    assert body["key_gen"] == 1
    assert body["argon_defaults"]["memory"] == 65536

    # step 2: complete creates user + device
    r = client.post(
        "/api/v1/invitations/complete",
        json={"invitation_id": inv_id, "redeem_secret": "rrr", **COMPLETE_KEYS},
    )
    assert r.status_code == 201, r.text
    joined = r.json()
    assert joined["device_token"]

    # the new device authenticates and sees its own identity + wrap
    me = client.get("/api/v1/whoami", headers=_auth(joined["device_token"])).json()
    assert me["name"] == "kolya"
    assert me["role"] == "editor"
    keys = client.get(
        "/api/v1/account/keys", headers=_auth(joined["device_token"])
    ).json()
    assert keys["wrapped_ak"] == "a29seWF3cmFw"
    assert keys["salt"] == "a29seWFzYWx0MTIzNDU2Nzg="

    # owner still sees their own wrap (per-user isolation)
    owner_keys = client.get("/api/v1/account/keys", headers=_auth(token)).json()
    assert owner_keys["wrapped_ak"] == "dGVzdHdyYXBwZWRhazEyMzQ1Njc4OTAxMjM0NTY="

    # invitation burned: sealed blob gone, reuse refused
    r = client.post(
        "/api/v1/invitations/redeem",
        json={"invitation_id": inv_id, "redeem_secret": "rrr"},
    )
    assert r.status_code == 404
    users = client.get("/api/v1/users", headers=_auth(token)).json()
    assert {u["name"] for u in users["users"]} == {"owner", "kolya"}


def test_redeem_with_wrong_secret_is_404(bootstrapped_client, team_mode):
    client, token, _ = bootstrapped_client
    inv_id = _invite(client, token).json()["invitation_id"]
    r = client.post(
        "/api/v1/invitations/redeem",
        json={"invitation_id": inv_id, "redeem_secret": "wrong"},
    )
    assert r.status_code == 404


def test_invite_of_existing_user_conflicts(bootstrapped_client, team_mode):
    client, token, _ = bootstrapped_client
    assert _invite(client, token, name="owner").status_code == 409


def test_invite_requires_owner_role(bootstrapped_client, team_mode):
    client, token, _ = bootstrapped_client
    inv_id = _invite(client, token, redeem_secret="s2").json()["invitation_id"]
    r = client.post(
        "/api/v1/invitations/complete",
        json={"invitation_id": inv_id, "redeem_secret": "s2", **COMPLETE_KEYS},
    )
    editor_token = r.json()["device_token"]
    r = _invite(client, editor_token, name="third", redeem_secret="s3")
    assert r.status_code == 403


def test_invite_refused_during_rotation(bootstrapped_client, team_mode):
    client, token, _ = bootstrapped_client
    client.post(
        "/api/v1/account/rotate/begin",
        json={"new_key_gen": 2, "nonce_ak": "bjI=", "wrapped_ak": "dzI="},
        headers=_auth(token),
    )
    assert _invite(client, token).status_code == 409


def test_expired_invitation_is_rejected(bootstrapped_client, team_mode):
    client, token, _ = bootstrapped_client
    inv_id = _invite(client, token, ttl="0s").json()["invitation_id"]
    r = client.post(
        "/api/v1/invitations/redeem",
        json={"invitation_id": inv_id, "redeem_secret": "rrr"},
    )
    assert r.status_code == 404


def _join_as_editor(client, token, name="vera", secret="sv"):
    inv_id = _invite(client, token, name=name, redeem_secret=secret).json()["invitation_id"]
    r = client.post(
        "/api/v1/invitations/complete",
        json={"invitation_id": inv_id, "redeem_secret": secret, **COMPLETE_KEYS},
    )
    return r.json()


def test_viewer_is_read_only(bootstrapped_client, team_mode):
    client, token, _ = bootstrapped_client
    client.post("/api/v1/apps", json={"name": "a"}, headers=_auth(token))
    client.post("/api/v1/apps/a/envs", json={"name": "dev"}, headers=_auth(token))
    client.post(
        "/api/v1/apps/a/envs/dev/revisions",
        json={"blob": "v1:eA==:eQ==", "content_hash": None, "parent_rev": 0},
        headers=_auth(token),
    )

    inv_id = _invite(client, token, name="ro", role="viewer", redeem_secret="sv").json()[
        "invitation_id"
    ]
    viewer = client.post(
        "/api/v1/invitations/complete",
        json={"invitation_id": inv_id, "redeem_secret": "sv", **COMPLETE_KEYS},
    ).json()
    vt = viewer["device_token"]

    # reads work
    assert (
        client.get("/api/v1/apps/a/envs/dev/revisions/last", headers=_auth(vt)).status_code
        == 200
    )
    # writes forbidden
    assert (
        client.post(
            "/api/v1/apps/a/envs/dev/revisions",
            json={"blob": "v1:eA==:eQ==", "content_hash": None, "parent_rev": 1},
            headers=_auth(vt),
        ).status_code
        == 403
    )
    assert (
        client.post("/api/v1/apps", json={"name": "b"}, headers=_auth(vt)).status_code
        == 403
    )


def test_editor_writes_but_cannot_delete_or_rotate(bootstrapped_client, team_mode):
    client, token, _ = bootstrapped_client
    client.post("/api/v1/apps", json={"name": "a"}, headers=_auth(token))
    client.post("/api/v1/apps/a/envs", json={"name": "dev"}, headers=_auth(token))

    editor = _join_as_editor(client, token)
    et = editor["device_token"]

    # push allowed
    assert (
        client.post(
            "/api/v1/apps/a/envs/dev/revisions",
            json={"blob": "v1:eA==:eQ==", "content_hash": None, "parent_rev": 0},
            headers=_auth(et),
        ).status_code
        == 201
    )
    # deletes / rotation are owner-only
    assert client.delete("/api/v1/apps/a", headers=_auth(et)).status_code == 403
    assert (
        client.post(
            "/api/v1/account/rotate/begin",
            json={"new_key_gen": 2, "nonce_ak": "bg==", "wrapped_ak": "dw=="},
            headers=_auth(et),
        ).status_code
        == 403
    )


def test_role_change_and_last_owner_protection(bootstrapped_client, team_mode):
    client, token, _ = bootstrapped_client
    editor = _join_as_editor(client, token)
    editor_user_id = editor["user_id"]

    # promote editor to owner
    r = client.patch(
        f"/api/v1/users/{editor_user_id}",
        json={"role": "owner"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    # find owner's own user id
    users = client.get("/api/v1/users", headers=_auth(token)).json()["users"]
    owner_id = next(u["id"] for u in users if u["name"] == "owner")
    # demote original owner: allowed now (another owner exists)
    assert (
        client.patch(
            f"/api/v1/users/{owner_id}", json={"role": "viewer"}, headers=_auth(token)
        ).status_code
        == 200
    )
    # vera is the last owner — demoting her is refused
    assert (
        client.patch(
            f"/api/v1/users/{editor_user_id}",
            json={"role": "editor"},
            headers=_auth(editor["device_token"]),
        ).status_code
        == 409
    )


def test_user_removal_revokes_devices_and_wraps(bootstrapped_client, team_mode):
    client, token, _ = bootstrapped_client
    editor = _join_as_editor(client, token)
    et, uid = editor["device_token"], editor["user_id"]

    r = client.delete(f"/api/v1/users/{uid}", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["devices_revoked"] == 1
    assert body["rotation_required"] is True

    # removed user's device token is dead
    assert client.get("/api/v1/whoami", headers=_auth(et)).status_code == 401
    # wraps are gone from the roster
    users = client.get("/api/v1/users", headers=_auth(token)).json()["users"]
    vera = next(u for u in users if u["name"] == "vera")
    assert vera["status"] == "removed"

    # last-owner removal refused
    owner_id = next(u["id"] for u in users if u["name"] == "owner")
    assert (
        client.delete(f"/api/v1/users/{owner_id}", headers=_auth(token)).status_code
        == 409
    )


def test_audit_reports_user_names(bootstrapped_client, team_mode):
    client, token, _ = bootstrapped_client
    client.post("/api/v1/apps", json={"name": "a"}, headers=_auth(token))
    client.post("/api/v1/apps/a/envs", json={"name": "dev"}, headers=_auth(token))
    editor = _join_as_editor(client, token)
    client.post(
        "/api/v1/apps/a/envs/dev/revisions",
        json={"blob": "v1:eA==:eQ==", "content_hash": None, "parent_rev": 0},
        headers=_auth(editor["device_token"]),
    )
    events = client.get("/api/v1/audit", headers=_auth(token)).json()["events"]
    push = next(e for e in events if e["action"] == "push")
    assert push["user"] == "vera"
    created = next(e for e in events if e["action"] == "app.created")
    assert created["user"] == "owner"
