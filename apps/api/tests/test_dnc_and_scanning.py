import httpx
import pytest

from app.core import scanning
from app.core.errors import AppError
from app.modules.dnc import service as dnc
from tests.test_telephony import E164, _call, _configure, _env, _setup  # noqa: F401  (_env: autouse fixture)

D = "/api/v1/compliance/dnc"


def _import(client, h, text, country="IN"):
    return client.post(f"{D}/import", headers=h, data={"country": country},
                       files={"file": ("ncpr.csv", text.encode(), "text/csv")})


def test_imported_registry_blocks_listed_number(client, monkeypatch):
    _configure(monkeypatch)
    s = _setup(client, "DNC Org")
    r = _import(client, s["h"], "phone\n09876543210\n+91 99999 11111\nnot-a-number\n")
    assert r.status_code == 201, r.text
    assert r.json()["imported"] == 2 and r.json()["rejected"] == 1
    c = _call(client, s)
    assert c.status_code == 422 and "dnc_registry_listed:IN" in c.text
    st = client.get(f"{D}/status", headers=s["h"]).json()
    assert next(x for x in st["countries"] if x["country"] == "IN")["fresh"] is True


def test_unchecked_registry_blocks_when_enforced(client, monkeypatch):
    _configure(monkeypatch)
    s = _setup(client, "DNC Enforce")
    monkeypatch.setenv("DNC_ENFORCE", "true")
    c = _call(client, s)
    assert c.status_code == 422 and "dnc_registry_not_checked:IN" in c.text
    _import(client, s["h"], "+919000000000\n")  # fresh file without this number -> allowed
    assert _call(client, s).status_code == 201


def test_registry_api_listed_and_unavailable(client, monkeypatch):
    _configure(monkeypatch)
    s = _setup(client, "DNC Api")
    monkeypatch.setenv("DNC_API_URL", "https://dnc.example.test/check")
    monkeypatch.setattr(dnc, "http_transport", httpx.MockTransport(
        lambda req: httpx.Response(200, json={"listed": req.url.params["phone"] == E164})))
    assert "dnc_registry_listed:IN" in _call(client, s).text
    monkeypatch.setattr(dnc, "http_transport", httpx.MockTransport(lambda req: httpx.Response(500)))
    assert "dnc_registry_unavailable" in _call(client, s).text


def test_registry_import_requires_admin_and_known_country(client, monkeypatch):
    s = _setup(client, "DNC Perm")
    assert _import(client, s["h"], "1\n", country="ZZ").status_code == 422


def test_scanner_rules(monkeypatch):
    monkeypatch.delenv("CLAMAV_HOST", raising=False)
    monkeypatch.setenv("CLAMAV_REQUIRED", "")
    assert scanning.scan_bytes(b"x") == "unscanned"  # development
    monkeypatch.setenv("CLAMAV_REQUIRED", "true")
    with pytest.raises(AppError) as e:
        scanning.scan_bytes(b"x")
    assert e.value.code == "scanner_not_configured"
    monkeypatch.setenv("CLAMAV_HOST", "clamav")
    monkeypatch.setattr(scanning, "clamd_scan", lambda *a, **k: "stream: OK")
    assert scanning.scan_bytes(b"x") == "clean"
    monkeypatch.setattr(scanning, "clamd_scan", lambda *a, **k: "stream: Eicar-Signature FOUND")
    with pytest.raises(AppError) as e:
        scanning.scan_bytes(b"x")
    assert e.value.code == "upload_infected"

    def down(*a, **k):
        raise OSError("refused")

    monkeypatch.setattr(scanning, "clamd_scan", down)
    with pytest.raises(AppError) as e:
        scanning.scan_bytes(b"x")
    assert e.value.code == "scanner_unavailable"


def test_infected_upload_rejected_end_to_end(client, monkeypatch):
    s = _setup(client, "Scan Org")
    monkeypatch.setenv("CLAMAV_HOST", "clamav")
    monkeypatch.setattr(scanning, "clamd_scan", lambda *a, **k: "stream: Eicar-Signature FOUND")
    r = client.post("/api/v1/discovery/import", headers=s["h"],
                    files={"file": ("x.csv", b"name\nAcme\n", "text/csv")})
    assert r.status_code == 422 and "upload_infected" in r.text
