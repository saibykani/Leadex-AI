import csv
import io
import json
import uuid
from datetime import timedelta

import httpx
import pytest

from app.core.db import tenant_session, utcnow
from app.modules.discovery import http as dhttp
from app.modules.discovery import service as dsvc
from app.modules.discovery import website_audit
from app.modules.discovery.models import BusinessSourceField, UsageRecord
from tests.conftest import register, tenant_headers

D = "/api/v1/discovery"
B = "/api/v1/businesses"

PLACES = {"places": [
    {"id": "place-1", "displayName": {"text": "Sunrise Dental"}, "formattedAddress": "1 MG Rd, Pune",
     "primaryType": "dentist", "nationalPhoneNumber": "098765 43210", "websiteUri": "https://sunrise.example",
     "location": {"latitude": 18.5, "longitude": 73.8},
     "addressComponents": [{"longText": "Pune", "types": ["locality"]},
                           {"longText": "India", "shortText": "IN", "types": ["country"]}]},
    {"id": "place-2", "displayName": {"text": "No Site Clinic"}, "formattedAddress": "2 FC Rd, Pune",
     "addressComponents": [{"longText": "Pune", "types": ["locality"]}]},
]}


@pytest.fixture
def mock_http(monkeypatch):
    calls: list[httpx.Request] = []
    handlers: dict = {}

    def handler(req: httpx.Request):
        calls.append(req)
        for prefix, fn in handlers.items():
            if str(req.url).startswith(prefix):
                return fn(req)
        raise httpx.ConnectError("no route", request=req)

    monkeypatch.setattr(dhttp, "transport", httpx.MockTransport(handler))
    monkeypatch.setattr(website_audit, "guard_target", lambda url: None)
    return calls, handlers


@pytest.fixture
def google(monkeypatch, mock_http):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")
    calls, handlers = mock_http
    handlers["https://places.googleapis.com/"] = lambda req: httpx.Response(200, json=PLACES)
    return calls, handlers


def _add_member(client, owner, role):
    other = register(client, f"Other {role}")
    r = client.post(f"/api/v1/organizations/{owner['org_id']}/members", headers=owner["headers"],
                    json={"email": other["email"], "role": role})
    assert r.status_code == 201, r.text
    return tenant_headers(other, owner["org_id"])


def _search(client, h, **criteria):
    return client.post(f"{D}/search", headers=h, json={"criteria": criteria})


def test_sources_and_google_not_configured(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    h = tenant_headers(register(client, "Disc Sources"))
    s = client.get(f"{D}/sources", headers=h).json()
    by = {x["source"]: x for x in s["sources"]}
    assert by["google_places"]["status"] == "not_configured"
    assert by["simulated"]["simulated"] is True and by["customer_import"]["supports_search"] is False
    r = _search(client, h, source="google_places", city="Pune")
    assert r.status_code == 409 and r.json()["error"]["code"] == "source_not_configured"
    assert _search(client, h, source="customer_import").status_code == 422
    assert client.get(f"{D}/jobs", headers=h).json()["total"] == 0  # nothing fabricated


def test_simulated_search_is_labelled_and_deduplicated(client):
    h = tenant_headers(register(client, "Disc Sim"))
    r = _search(client, h, source="simulated", city="Pune", industry="dental", limit=3)
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["status"] == "completed" and job["is_simulated"] and job["new_count"] == 3
    items = client.get(B, headers=h).json()["items"]
    assert len(items) == 3
    assert all(i["source"] == "simulated" and i["is_simulated"] and i["name"].startswith("Simulated Business")
               for i in items)
    again = _search(client, h, source="simulated", city="Pune", industry="dental", limit=3).json()
    assert again["new_count"] == 0 and again["duplicate_count"] == 3
    assert client.get(B, headers=h).json()["total"] == 3
    # no usage billed for simulated runs
    assert client.get(f"{D}/sources", headers=h).json()["requests_used_today"] == 0


def test_google_search_provenance_usage_and_export(client, google):
    calls, _ = google
    a = register(client, "Disc Google")
    h = tenant_headers(a)
    r = _search(client, h, source="google_places", city="Pune", country="in", industry="dental")
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["status"] == "completed" and job["results_count"] == 2 and job["cost_units"] == 1
    req = calls[0]
    assert req.headers["X-Goog-Api-Key"] == "test-key" and "places.id" in req.headers["X-Goog-FieldMask"]
    assert json.loads(req.content)["textQuery"] == "dental in Pune, IN"
    biz = {i["google_place_id"]: i for i in client.get(B, headers=h).json()["items"]}
    assert biz["place-1"]["website_status"] == "has_website" and biz["place-1"]["country"] == "IN"
    assert biz["place-2"]["website_status"] == "no_website_listed"
    assert [i["google_place_id"] for i in client.get(B, headers=h, params={"website_status": "no_website_listed"})
            .json()["items"]] == ["place-2"]
    detail = client.get(f"{B}/{biz['place-1']['id']}", headers=h).json()
    prov = {p["field"]: p for p in detail["provenance"]}
    assert prov["name"]["source"] == "google_places" and prov["name"]["retention_until"]
    assert prov["google_place_id"]["retention_until"] is None
    assert prov["industry"]["retention_until"] is None  # user-supplied label, not Google content
    # re-run: dedup on place_id, a second usage record
    again = _search(client, h, source="google_places", city="Pune").json()
    assert again["duplicate_count"] == 2 and again["new_count"] == 0
    assert client.get(f"{D}/sources", headers=h).json()["requests_used_today"] == 2
    # export: Google content blanked, place_id kept
    r = client.get(f"{D}/export", headers=h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = {row["google_place_id"]: row for row in csv.DictReader(io.StringIO(r.text))}
    assert rows["place-1"]["name"] == "" and rows["place-1"]["phone"] == "" and rows["place-1"]["website"] == ""
    assert rows["place-1"]["industry"] == "dental"


def test_google_error_marks_job_failed(client, google):
    _, handlers = google
    handlers["https://places.googleapis.com/"] = lambda req: httpx.Response(
        403, json={"error": {"message": "API key not valid"}})
    h = tenant_headers(register(client, "Disc GErr"))
    job = _search(client, h, source="google_places", city="Pune").json()
    assert job["status"] == "failed" and "403" in job["error"] and job["results_count"] == 0
    assert client.get(B, headers=h).json()["total"] == 0


def test_daily_budget_429(client, google, monkeypatch):
    monkeypatch.setenv("DISCOVERY_DAILY_REQUEST_BUDGET", "1")
    h = tenant_headers(register(client, "Disc Budget"))
    assert _search(client, h, source="google_places", city="Pune").status_code == 201
    r = _search(client, h, source="google_places", city="Pune")
    assert r.status_code == 429 and r.json()["error"]["code"] == "discovery_budget_exceeded"
    # simulated mode is not billable
    assert _search(client, h, source="simulated", city="Pune").status_code == 201


def test_csv_import_filters_and_dedup(client):
    h = tenant_headers(register(client, "Disc CSV"))
    data = ("name,industry,city,phone,website\nAlpha Bakery,bakery,Delhi,011 2345 6789,alpha.example\n"
            "Beta Gym,fitness,Goa,,\nAlpha Bakery Dup,bakery,Delhi,011-2345-6789,\n,,,,\n")
    r = client.post(f"{D}/import", headers=h, files={"file": ("leads.csv", data, "text/csv")})
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["source"] == "customer_import" and job["new_count"] == 2 and job["duplicate_count"] == 1
    assert client.get(B, headers=h, params={"industry": "bakery"}).json()["total"] == 1
    assert client.get(B, headers=h, params={"city": "goa"}).json()["total"] == 1
    assert client.get(B, headers=h, params={"q": "alpha"}).json()["total"] == 1
    assert client.get(B, headers=h, params={"website_status": "bogus"}).status_code == 422
    rows = list(csv.DictReader(io.StringIO(client.get(f"{D}/export", headers=h).text)))
    assert {r["name"] for r in rows} == {"Alpha Bakery", "Beta Gym"}  # customer data is exportable
    bad = client.post(f"{D}/import", headers=h, files={"file": ("x.csv", "foo,bar\n1,2\n", "text/csv")}).json()
    assert bad["status"] == "failed" and "name" in bad["error"]
    assert client.get(f"{D}/jobs/{job['id']}", headers=h).json()["new_count"] == 2


def _csv_business(client, h, website="https://shop.example", name="Shop One"):
    data = f"name,city,website\n{name},Pune,{website}\n"
    assert client.post(f"{D}/import", headers=h, files={"file": ("a.csv", data, "text/csv")}).status_code == 201
    return client.get(B, headers=h, params={"q": name}).json()["items"][0]


def test_website_audit_scores_and_explains(client, mock_http):
    _, handlers = mock_http
    html = ('<html><head><title>Shop</title><meta name="viewport" content="width=device-width">'
            '<meta name="description" content="Best shop"></head><body><a href="tel:+911234567890">Call</a>'
            '<a href="/ok">ok</a><a href="/missing">x</a><button>Book now</button></body></html>')

    def site(req):
        if req.url.path == "/missing":
            return httpx.Response(404)
        return httpx.Response(200, html=html)

    handlers["https://shop.example"] = site
    h = tenant_headers(register(client, "Disc Audit"))
    b = _csv_business(client, h)
    r = client.post(f"{B}/{b['id']}/audit", headers=h)
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["reachable"] and a["ssl_valid"] and a["mobile_viewport"] and a["has_cta"] and a["has_contact_info"]
    assert a["broken_links_checked"] == 2 and a["broken_links_found"] == 1
    assert a["score"] == 98 and all(f["explanation"] for f in a["findings"])
    d = client.get(f"{B}/{b['id']}", headers=h).json()
    assert d["business"]["website_status"] == "reachable" and len(d["audits"]) == 1
    assert d["verifications"][0]["method"] == "website_audit"


def test_audit_network_error_is_not_no_website(client, mock_http):
    calls, _ = mock_http  # no handler -> ConnectError for everything
    h = tenant_headers(register(client, "Disc Unreach"))
    b = _csv_business(client, h, website="https://down.example", name="Down Shop")
    a = client.post(f"{B}/{b['id']}/audit", headers=h).json()
    assert a["reachable"] is False and a["score"] is None and a["error"]
    assert len(calls) == 4  # 1 + 2 retries over https, then one plain-http attempt
    biz = client.get(f"{B}/{b['id']}", headers=h).json()["business"]
    assert biz["website_status"] == "unreachable_retry"
    no_site = _csv_business(client, h, website="", name="Nosite")
    assert client.post(f"{B}/{no_site['id']}/audit", headers=h).status_code == 422


def test_convert_to_lead_and_duplicate(client):
    h = tenant_headers(register(client, "Disc Convert"))
    b = _csv_business(client, h, website="https://conv.example", name="Conv Co")
    r = client.post(f"{B}/{b['id']}/convert-to-lead", headers=h)
    assert r.status_code == 201, r.text
    lead = client.get(f"/api/v1/leads/{r.json()['lead_id']}", headers=h).json()
    assert lead["status"] == "discovered" and lead["source"] == "discovery:customer_import"
    assert lead["business_name"] == "Conv Co"
    assert client.post(f"{B}/{b['id']}/convert-to-lead", headers=h).status_code == 409
    # another business with the same website domain collides with the existing lead
    data = "name,city,website\nOther Co,Mumbai,https://www.conv.example/about\n"
    client.post(f"{D}/import", headers=h, files={"file": ("b.csv", data, "text/csv")})
    items = client.get(B, headers=h).json()["items"]
    assert len(items) == 1  # dedup by website domain merged it into the same business


def test_saved_searches_crud(client):
    h = tenant_headers(register(client, "Disc Saved"))
    body = {"name": "Pune dentists", "criteria": {"source": "simulated", "city": "Pune"}, "schedule": "0 6 * * 1"}
    s = client.post(f"{D}/saved-searches", headers=h, json=body)
    assert s.status_code == 201, s.text
    sid = s.json()["id"]
    assert client.post(f"{D}/saved-searches", headers=h, json={**body, "schedule": "every day"}).status_code == 422
    r = client.patch(f"{D}/saved-searches/{sid}", headers=h, json={"name": "Renamed", "schedule": None})
    assert r.json()["name"] == "Renamed" and r.json()["schedule"] is None
    job = client.post(f"{D}/search", headers=h, json={"criteria": body["criteria"], "saved_search_id": sid}).json()
    assert job["saved_search_id"] == sid
    assert client.get(f"{D}/saved-searches/{sid}", headers=h).json()["last_run_at"]
    assert len(client.get(f"{D}/saved-searches", headers=h).json()) == 1
    assert client.delete(f"{D}/saved-searches/{sid}", headers=h).status_code == 204
    assert client.get(f"{D}/saved-searches/{sid}", headers=h).status_code == 404


def test_cross_tenant_isolation(client):
    a, b = register(client, "Disc Tenant A"), register(client, "Disc Tenant B")
    ha, hb = tenant_headers(a), tenant_headers(b)
    biz = _csv_business(client, ha, name="Secret Biz")
    job = client.get(f"{D}/jobs", headers=ha).json()["items"][0]
    sid = client.post(f"{D}/saved-searches", headers=ha,
                      json={"name": "x", "criteria": {"source": "simulated"}}).json()["id"]
    assert client.get(f"{B}/{biz['id']}", headers=hb).status_code == 404
    assert client.post(f"{B}/{biz['id']}/audit", headers=hb).status_code == 404
    assert client.post(f"{B}/{biz['id']}/convert-to-lead", headers=hb).status_code == 404
    assert client.get(f"{D}/jobs/{job['id']}", headers=hb).status_code == 404
    assert client.get(f"{D}/saved-searches/{sid}", headers=hb).status_code == 404
    assert client.patch(f"{D}/saved-searches/{sid}", headers=hb, json={"name": "y"}).status_code == 404
    assert client.delete(f"{D}/saved-searches/{sid}", headers=hb).status_code == 404
    assert client.get(B, headers=hb).json()["total"] == 0
    assert "Secret Biz" not in client.get(f"{D}/export", headers=hb).text
    assert client.post(f"{D}/search", headers=hb, json={"criteria": {"source": "simulated"},
                                                        "saved_search_id": sid}).status_code == 404
    # B cannot act on A's org at all
    assert client.get(B, headers=tenant_headers(b, a["org_id"])).status_code == 404


def test_rbac(client):
    owner = register(client, "Disc RBAC")
    biz = _csv_business(client, tenant_headers(owner), name="Rbac Biz")
    viewer = _add_member(client, owner, "Viewer")
    rep = _add_member(client, owner, "Sales Rep")
    assert client.get(B, headers=viewer).status_code == 200
    assert _search(client, viewer, source="simulated").status_code == 403
    assert client.post(f"{D}/import", headers=viewer,
                       files={"file": ("a.csv", "name\nX\n", "text/csv")}).status_code == 403
    assert client.post(f"{D}/saved-searches", headers=viewer,
                       json={"name": "x", "criteria": {"source": "simulated"}}).status_code == 403
    assert client.post(f"{B}/{biz['id']}/audit", headers=rep).status_code == 403
    assert client.post(f"{B}/{biz['id']}/convert-to-lead", headers=rep).status_code == 403
    assert client.get(f"{D}/sources", headers=tenant_headers(register(client, "Nobody"), owner["org_id"])
                      ).status_code == 404


def test_purge_expired_google_fields(client, google):
    h = tenant_headers(register(client, "Disc Purge"))
    _search(client, h, source="google_places", city="Pune", industry="dental")
    n = dsvc.purge_expired_provider_fields_all_tenants(now=utcnow() + timedelta(days=31))
    assert n > 0
    item = next(i for i in client.get(B, headers=h).json()["items"] if i["google_place_id"] == "place-1")
    assert item["name"] is None and item["phone"] is None and item["website"] is None
    assert item["google_place_id"] == "place-1" and item["industry"] == "dental"
    with tenant_session(uuid.UUID(h["X-Organization-Id"])) as db:
        purged = db.query(BusinessSourceField).filter(BusinessSourceField.field == "google_place_id",
                                                      BusinessSourceField.value == "place-1").count()
        assert purged >= 1 and db.query(UsageRecord).count() >= 1


def test_csv_import_country_names_map_to_iso_codes():
    from app.modules.discovery.adapters.csv_import import CsvImportAdapter
    data = b"name,country\nA,United Kingdom\nB,uae\nC,in\nD,Atlantis\n"
    recs = CsvImportAdapter().parse(data).records
    assert [r.fields.get("country") for r in recs] == ["GB", "AE", "IN", None]
