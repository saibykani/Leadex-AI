from tests.conftest import register

A = "/api/v1/auth"
H = {"X-Requested-With": "leadex"}


def test_login_sets_httponly_cookie_and_refresh_uses_it(client):
    acc = register(client)
    r = client.post(f"{A}/login", json={"email": acc["email"], "password": acc["password"]})
    sc = r.headers.get("set-cookie", "")
    assert "lx_refresh=" in sc and "HttpOnly" in sc and "Path=/api/v1/auth" in sc and "samesite=lax" in sc.lower()
    # cookie alone (no custom header) is refused: protects against cross-site request forgery
    assert client.post(f"{A}/refresh").status_code == 401
    r2 = client.post(f"{A}/refresh", headers=H)
    assert r2.status_code == 200 and r2.json()["access_token"]
    # rotation: the new cookie replaced the old one; the old token is single-use
    old = r.json()["refresh_token"]
    assert client.post(f"{A}/refresh", json={"refresh_token": old}).status_code == 401
    assert client.post(f"{A}/refresh", headers=H).status_code == 200


def test_logout_clears_cookie_and_revokes(client):
    acc = register(client)
    client.post(f"{A}/login", json={"email": acc["email"], "password": acc["password"]})
    r = client.post(f"{A}/logout", headers=H)
    assert r.status_code == 204 and 'lx_refresh=""' in r.headers.get("set-cookie", "")
    assert client.post(f"{A}/refresh", headers=H).status_code == 401


def test_body_token_still_works_for_api_clients(client):
    acc = register(client)
    client.cookies.clear()
    r = client.post(f"{A}/refresh", json={"refresh_token": acc["tokens"]["refresh_token"]})
    assert r.status_code == 200
