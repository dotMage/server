"""AK rotation endpoint tests (spec L)."""


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _seed_app(client, token, app="myapp", env="dev", revs=2):
    client.post("/api/v1/apps", json={"name": app}, headers=_auth(token))
    client.post(f"/api/v1/apps/{app}/envs", json={"name": env}, headers=_auth(token))
    for i in range(revs):
        r = client.post(
            f"/api/v1/apps/{app}/envs/{env}/revisions",
            json={"blob": f"v1:bm9uY2U=:Y3Q{i}=", "content_hash": None, "parent_rev": i},
            headers=_auth(token),
        )
        assert r.status_code == 201, r.text


def _begin(client, token, gen=2):
    return client.post(
        "/api/v1/account/rotate/begin",
        json={"new_key_gen": gen, "nonce_ak": "bm9uY2Uy", "wrapped_ak": "d3JhcDI="},
        headers=_auth(token),
    )


def test_full_rotation_cycle(bootstrapped_client):
    client, token, _ = bootstrapped_client
    _seed_app(client, token, revs=3)

    r = _begin(client, token)
    assert r.status_code == 200
    assert r.json() == {"new_key_gen": 2, "stale_count": 3}

    # status lists stale revisions and the pending wrap
    r = client.get("/api/v1/account/rotate", headers=_auth(token))
    body = r.json()
    assert body["in_progress"] is True
    assert body["stale_count"] == 3
    assert body["pending_wrapped_ak"] == "d3JhcDI="
    assert {s["rev_number"] for s in body["stale"]} == {1, 2, 3}

    # swap each blob
    for s in body["stale"]:
        r = client.put(
            f"/api/v1/apps/{s['app']}/envs/{s['env']}/revisions/{s['rev_number']}/blob",
            json={"blob": "v1:bm9uY2Uy:bmV3Y3Q=", "key_gen": 2},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text

    r = client.post("/api/v1/account/rotate/complete", headers=_auth(token))
    assert r.status_code == 200
    assert r.json() == {"current_key_gen": 2}

    # cutover: keys now serve gen 2 wrap, pulls report key_gen 2
    keys = client.get("/api/v1/account/keys", headers=_auth(token)).json()
    assert keys["key_gen"] == 2
    assert keys["wrapped_ak"] == "d3JhcDI="
    pull = client.get(
        "/api/v1/apps/myapp/envs/dev/revisions/last", headers=_auth(token)
    ).json()
    assert pull["key_gen"] == 2
    assert pull["blob"] == "v1:bm9uY2Uy:bmV3Y3Q="


def test_push_and_rollback_refused_during_rotation(bootstrapped_client):
    client, token, _ = bootstrapped_client
    _seed_app(client, token, revs=1)
    assert _begin(client, token).status_code == 200

    r = client.post(
        "/api/v1/apps/myapp/envs/dev/revisions",
        json={"blob": "v1:eA==:eQ==", "content_hash": None, "parent_rev": 1},
        headers=_auth(token),
    )
    assert r.status_code == 409
    assert "rotation" in r.json()["error"]["message"].lower()

    r = client.post(
        "/api/v1/apps/myapp/envs/dev/rollback",
        json={"to_rev": 1},
        headers=_auth(token),
    )
    assert r.status_code == 409


def test_put_blob_outside_rotation_is_405(bootstrapped_client):
    client, token, _ = bootstrapped_client
    _seed_app(client, token, revs=1)
    r = client.put(
        "/api/v1/apps/myapp/envs/dev/revisions/1/blob",
        json={"blob": "v1:eA==:eQ==", "key_gen": 2},
        headers=_auth(token),
    )
    assert r.status_code == 405


def test_begin_is_idempotent_and_conflicts(bootstrapped_client):
    client, token, _ = bootstrapped_client
    _seed_app(client, token, revs=1)
    assert _begin(client, token, gen=2).status_code == 200
    # same target gen → idempotent resume
    r = _begin(client, token, gen=2)
    assert r.status_code == 200
    assert r.json()["stale_count"] == 1
    # different target gen → conflict
    assert _begin(client, token, gen=3).status_code == 409


def test_complete_refused_while_stale_remain(bootstrapped_client):
    client, token, _ = bootstrapped_client
    _seed_app(client, token, revs=2)
    assert _begin(client, token).status_code == 200
    r = client.post("/api/v1/account/rotate/complete", headers=_auth(token))
    assert r.status_code == 409
    assert "2" in r.json()["error"]["message"]


def test_put_blob_with_wrong_gen_is_conflict(bootstrapped_client):
    client, token, _ = bootstrapped_client
    _seed_app(client, token, revs=1)
    assert _begin(client, token).status_code == 200
    r = client.put(
        "/api/v1/apps/myapp/envs/dev/revisions/1/blob",
        json={"blob": "v1:eA==:eQ==", "key_gen": 5},
        headers=_auth(token),
    )
    assert r.status_code == 409


def test_rollback_preserves_source_key_gen(bootstrapped_client):
    client, token, _ = bootstrapped_client
    _seed_app(client, token, revs=1)
    r = client.post(
        "/api/v1/apps/myapp/envs/dev/rollback",
        json={"to_rev": 1},
        headers=_auth(token),
    )
    assert r.status_code == 201
    pull = client.get(
        "/api/v1/apps/myapp/envs/dev/revisions/2", headers=_auth(token)
    ).json()
    assert pull["key_gen"] == 1


def test_reads_work_during_rotation(bootstrapped_client):
    client, token, _ = bootstrapped_client
    _seed_app(client, token, revs=1)
    assert _begin(client, token).status_code == 200
    r = client.get(
        "/api/v1/apps/myapp/envs/dev/revisions/last", headers=_auth(token)
    )
    assert r.status_code == 200
    assert r.json()["key_gen"] == 1
