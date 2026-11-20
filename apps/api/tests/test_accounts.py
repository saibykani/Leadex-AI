from urllib.parse import parse_qs, urlparse

from tests.conftest import register, tenant_headers

A = "/api/v1/auth"


def _tok(link):
    return parse_qs(urlparse(link).query)["token"][0]


def test_password_reset_flow_and_no_enumeration(client):
    acc = register(client)
    r = client.post(f"{A}/password/forgot", json={"email": "nobody-here@example.com"})
    assert r.status_code == 202 and r.json()["dev_link"] is None
    r = client.post(f"{A}/password/forgot", json={"email": acc["email"]})
    assert r.status_code == 202 and r.json()["simulated"] is True
    token = _tok(r.json()["dev_link"])
    assert client.post(f"{A}/password/reset", json={"token": token, "password": "short"}).status_code == 422
    assert client.post(f"{A}/password/reset", json={"token": token, "password": "BrandNewPass99"}).status_code == 204
    # single use
    assert client.post(f"{A}/password/reset", json={"token": token, "password": "BrandNewPass99"}).status_code == 400
    # old refresh token was revoked; old password fails, new works
    assert client.post(f"{A}/refresh", json={"refresh_token": acc["tokens"]["refresh_token"]}).status_code == 401
    assert client.post(f"{A}/login", json={"email": acc["email"], "password": acc["password"]}).status_code == 401
    assert client.post(f"{A}/login", json={"email": acc["email"], "password": "BrandNewPass99"}).status_code == 200


def test_email_verification(client):
    acc = register(client)
    assert client.get(f"{A}/me", headers=acc["headers"]).json()["user"]["email_verified_at"] is None
    r = client.post(f"{A}/email/verify/request", headers=acc["headers"])
    assert r.status_code == 200
    assert client.post(f"{A}/email/verify", json={"token": _tok(r.json()["dev_link"])}).status_code == 204
    assert client.get(f"{A}/me", headers=acc["headers"]).json()["user"]["email_verified_at"] is not None
    assert client.post(f"{A}/email/verify", json={"token": "x" * 40}).status_code == 400


def test_invite_new_user_and_existing_user(client):
    owner = register(client)
    org = owner["org_id"]
    r = client.post(f"/api/v1/organizations/{org}/invitations", headers=tenant_headers(owner),
                    json={"email": "newbie@example.com", "role": "Sales Rep"})
    assert r.status_code == 201, r.text
    token = _tok(r.json()["dev_link"])
    pv = client.post(f"{A}/invites/preview", json={"token": token}).json()
    assert pv["email"] == "newbie@example.com" and pv["account_exists"] is False
    assert len(client.get(f"/api/v1/organizations/{org}/invitations", headers=tenant_headers(owner)).json()) == 1
    assert client.post(f"{A}/invites/accept", json={"token": token}).status_code == 422
    r = client.post(f"{A}/invites/accept", json={"token": token, "full_name": "New Bie", "password": "NewbiePass123"})
    assert r.status_code == 204, r.text
    login = client.post(f"{A}/login", json={"email": "newbie@example.com", "password": "NewbiePass123"}).json()
    me = client.get(f"{A}/me", headers={"Authorization": f"Bearer {login['access_token']}"}).json()
    assert [m["organization"]["id"] for m in me["memberships"]] == [org]

    # existing user must be signed in as the invited email
    other = register(client, org="Other Co")
    r = client.post(f"/api/v1/organizations/{org}/invitations", headers=tenant_headers(owner),
                    json={"email": other["email"], "role": "Sales Rep"})
    t2 = _tok(r.json()["dev_link"])
    assert client.post(f"{A}/invites/accept", json={"token": t2}).status_code == 401
    assert client.post(f"{A}/invites/accept", json={"token": t2}, headers=other["headers"]).status_code == 204


def test_invite_requires_permission_and_revocation(client):
    owner = register(client)
    outsider = register(client, org="Elsewhere")
    url = f"/api/v1/organizations/{owner['org_id']}/invitations"
    assert client.post(url, headers=tenant_headers(outsider, owner["org_id"]),
                       json={"email": "x@example.com"}).status_code in (403, 404)
    r = client.post(url, headers=tenant_headers(owner), json={"email": "y@example.com"})
    inv, token = r.json()["invite"]["id"], _tok(r.json()["dev_link"])
    assert client.delete(f"{url}/{inv}", headers=tenant_headers(owner)).status_code == 204
    assert client.post(f"{A}/invites/preview", json={"token": token}).status_code == 400


def test_sessions_list_and_revoke_others(client):
    acc = register(client)
    second = client.post(f"{A}/login", json={"email": acc["email"], "password": acc["password"]}).json()
    rows = client.get(f"{A}/sessions", headers=acc["headers"]).json()
    assert len(rows) == 2
    r = client.post(f"{A}/sessions/revoke-others", headers=acc["headers"],
                    json={"keep_refresh_token": second["refresh_token"]})
    assert r.json()["revoked"] == 1
    assert client.post(f"{A}/refresh", json={"refresh_token": acc["tokens"]["refresh_token"]}).status_code == 401
    assert client.post(f"{A}/refresh", json={"refresh_token": second["refresh_token"]}).status_code == 200
