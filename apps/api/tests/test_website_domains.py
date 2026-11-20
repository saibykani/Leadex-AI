import pytest

from app.modules.websites import domains
from tests.conftest import register, tenant_headers

W = "/api/v1/websites"
SITE = "/api/v1/public/custom-site"
ASK = "/api/v1/public/domain-check"
BIZ = {"name": "Sunrise Dental", "industry": "Dental clinic", "city": "Pune"}


@pytest.fixture
def txt(monkeypatch):
    """Fake DNS: map of record name -> list of TXT values."""
    records: dict[str, list[str]] = {}
    monkeypatch.setattr(domains, "lookup_txt", lambda name: records.get(name, []))
    return records


def _site(client, h):
    r = client.post(f"{W}/generate", headers=h, json={"template_key": "clinic", "business": BIZ})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _publish(client, h, pid):
    assert client.post(f"{W}/{pid}/approve", headers=h).status_code == 200
    assert client.post(f"{W}/{pid}/publish", headers=h).status_code == 200


def test_set_domain_and_instructions(client):
    a = register(client, "Dom A")
    h = tenant_headers(a)
    pid = _site(client, h)
    assert client.get(f"{W}/{pid}/domain", headers=h).json()["status"] == "none"
    r = client.put(f"{W}/{pid}/domain", headers=h, json={"domain": "WWW.Sunrise-Dental.example."})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["domain"] == "www.sunrise-dental.example" and d["status"] == "pending"
    assert d["record_name"] == "_leadex-verify.www.sunrise-dental.example" and d["record_type"] == "TXT"
    assert len(d["record_value"]) >= 16
    assert client.get(f"{W}/{pid}/domain", headers=h).json()["record_value"] == d["record_value"]
    for bad in ("https://x.example", "nodot", "a b.example", "1.2.3.4", "x.example/path", "-a.example"):
        assert client.put(f"{W}/{pid}/domain", headers=h, json={"domain": bad}).status_code == 422, bad


def test_verification_requires_txt_record(client, txt):
    a = register(client, "Dom Verify")
    h = tenant_headers(a)
    pid = _site(client, h)
    assert client.post(f"{W}/{pid}/domain/verify", headers=h).status_code == 409  # no domain yet
    d = client.put(f"{W}/{pid}/domain", headers=h, json={"domain": "verify.example"}).json()
    r = client.post(f"{W}/{pid}/domain/verify", headers=h).json()
    assert r["status"] == "pending" and "not found" in r["message"]
    txt[d["record_name"]] = ["some-other-value"]
    assert client.post(f"{W}/{pid}/domain/verify", headers=h).json()["status"] == "pending"
    txt[d["record_name"]] = ["unrelated", d["record_value"]]
    r = client.post(f"{W}/{pid}/domain/verify", headers=h).json()
    assert r["status"] == "verified" and r["verified_at"]
    assert client.get(f"{W}/{pid}", headers=h).json()["domain_verification_status"] == "verified"
    # changing the domain resets verification and issues a new token
    d2 = client.put(f"{W}/{pid}/domain", headers=h, json={"domain": "other.example"}).json()
    assert d2["status"] == "pending" and d2["record_value"] != d["record_value"] and d2["verified_at"] is None


def test_host_header_serving_needs_verified_and_published(client, txt):
    a = register(client, "Dom Serve")
    h = tenant_headers(a)
    pid = _site(client, h)
    host = {"Host": "shop.example"}
    assert client.get(SITE, headers=host).status_code == 404  # unknown domain
    d = client.put(f"{W}/{pid}/domain", headers=h, json={"domain": "shop.example"}).json()
    _publish(client, h, pid)
    assert client.get(SITE, headers=host).status_code == 404  # published but not verified
    assert client.get(ASK, params={"domain": "shop.example"}).status_code == 404
    txt[d["record_name"]] = [d["record_value"]]
    assert client.post(f"{W}/{pid}/domain/verify", headers=h).json()["status"] == "verified"
    r = client.get(SITE, headers={"Host": "SHOP.example:443"})
    assert r.status_code == 200 and "Sunrise Dental" in r.text
    assert r.headers["content-type"].startswith("text/html")
    assert client.get(SITE, headers={"Host": "evil.example"}).status_code == 404
    # verified but unpublished (second project): not served
    pid2 = _site(client, h)
    d2 = client.put(f"{W}/{pid2}/domain", headers=h, json={"domain": "draft.example"}).json()
    txt[d2["record_name"]] = [d2["record_value"]]
    client.post(f"{W}/{pid2}/domain/verify", headers=h)
    assert client.get(SITE, headers={"Host": "draft.example"}).status_code == 404
    # removing the domain stops serving
    assert client.delete(f"{W}/{pid}/domain", headers=h).status_code == 204
    assert client.get(SITE, headers=host).status_code == 404
    assert client.get(f"{W}/{pid}/domain", headers=h).json()["status"] == "none"


def test_ask_endpoint(client, txt):
    a = register(client, "Dom Ask")
    h = tenant_headers(a)
    pid = _site(client, h)
    d = client.put(f"{W}/{pid}/domain", headers=h, json={"domain": "ask.example"}).json()
    assert client.get(ASK, params={"domain": "ask.example"}).status_code == 404
    assert client.get(ASK).status_code == 404
    txt[d["record_name"]] = [d["record_value"]]
    client.post(f"{W}/{pid}/domain/verify", headers=h)
    assert client.get(ASK, params={"domain": "ask.example"}).status_code == 200
    assert client.get(ASK, params={"domain": "ASK.example"}).status_code == 200
    assert client.get(ASK, params={"domain": "nope.example"}).status_code == 404


def test_tenant_isolation(client, txt):
    a = register(client, "Dom Iso A")
    b = register(client, "Dom Iso B")
    ha, hb = tenant_headers(a), tenant_headers(b)
    pa, pb = _site(client, ha), _site(client, hb)
    assert client.put(f"{W}/{pa}/domain", headers=ha, json={"domain": "mine.example"}).status_code == 200
    r = client.put(f"{W}/{pb}/domain", headers=hb, json={"domain": "mine.example"})
    assert r.status_code == 409
    # B cannot see or change A's project domain
    assert client.get(f"{W}/{pa}/domain", headers=hb).status_code == 404
    assert client.put(f"{W}/{pa}/domain", headers=hb, json={"domain": "x.example"}).status_code == 404
    assert client.post(f"{W}/{pa}/domain/verify", headers=hb).status_code == 404
    assert client.delete(f"{W}/{pa}/domain", headers=hb).status_code == 404
    assert client.get(f"{W}/{pa}/domain", headers=ha).json()["domain"] == "mine.example"
