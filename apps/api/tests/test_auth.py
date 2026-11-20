from tests.conftest import register


def test_health(client):
    assert client.get("/health").json()["outbound_mode"] == "simulated"
    r = client.get("/health/ready")
    assert r.status_code == 200 and r.json()["checks"]["database"] == "ok"


def test_register_creates_owner_membership(client):
    acc = register(client)
    me = client.get("/api/v1/auth/me", headers=acc["headers"]).json()
    m = me["memberships"][0]
    assert m["role"] == "Owner"
    assert "members:write" in m["permissions"]
    assert m["organization"]["country_code"] == "IN"


def test_duplicate_email_rejected(client):
    acc = register(client)
    r = client.post("/api/v1/auth/register", json={
        "email": acc["email"].upper(), "password": "An0therPassword", "full_name": "X", "organization_name": "Other",
    })
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"


def test_weak_password_rejected(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "weak@example.com", "password": "short", "full_name": "X", "organization_name": "Org",
    })
    assert r.status_code == 422


def test_login_and_wrong_password(client):
    acc = register(client)
    ok = client.post("/api/v1/auth/login", json={"email": acc["email"], "password": acc["password"]})
    assert ok.status_code == 200 and ok.json()["access_token"]
    bad = client.post("/api/v1/auth/login", json={"email": acc["email"], "password": "wrongpassword1"})
    assert bad.status_code == 401
    unknown = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrongpassword1"})
    assert unknown.status_code == 401
    assert bad.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_refresh_rotation_and_logout(client):
    acc = register(client)
    rt = acc["tokens"]["refresh_token"]
    r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": rt})
    assert r1.status_code == 200
    # old refresh token is single use
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": rt}).status_code == 401
    new_rt = r1.json()["refresh_token"]
    assert client.post("/api/v1/auth/logout", json={"refresh_token": new_rt}).status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": new_rt}).status_code == 401


def test_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_injection_payload_is_inert(client):
    r = client.post("/api/v1/auth/login", json={"email": "a@b.com' OR '1'='1", "password": "x"})
    assert r.status_code == 422
    r = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "' OR 1=1 --"})
    assert r.status_code == 401


def test_login_rate_limited(client):
    codes = [client.post("/api/v1/auth/login", json={"email": "rl@example.com", "password": "x"}).status_code
             for _ in range(25)]
    assert 429 in codes
