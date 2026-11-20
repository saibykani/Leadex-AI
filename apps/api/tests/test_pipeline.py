"""Lead pipeline: Google photo references + proxy, business images, website images, outcome extraction, run."""
import json
import uuid
from urllib.parse import unquote

import httpx
import pytest
from sqlalchemy import func, select

from app.core.db import tenant_session
from app.modules.agents import config as ai_config
from app.modules.discovery import http as dhttp
from app.modules.discovery import website_audit
from app.modules.discovery.adapters import google_places
from app.modules.discovery.models import BusinessSourceField
from app.modules.pipeline import extraction
from app.modules.pipeline.models import BusinessImage, ConversationOutcome
from tests.conftest import register, tenant_headers

D = "/api/v1/discovery"
B = "/api/v1/businesses"
P = "/api/v1/pipeline"

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PHOTO_NAME = "places/place-9/photos/AbCdEf123"
PLACES = {"places": [{
    "id": "place-9", "displayName": {"text": "Lotus Bakery"}, "formattedAddress": "9 MG Rd, Pune",
    "primaryType": "bakery", "nationalPhoneNumber": "098765 11111", "websiteUri": "https://lotus.example",
    "addressComponents": [{"longText": "Pune", "types": ["locality"]},
                          {"longText": "India", "shortText": "IN", "types": ["country"]}],
    "photos": [{"name": PHOTO_NAME, "widthPx": 1200, "heightPx": 800,
                "authorAttributions": [{"displayName": "Asha K", "uri": "https://maps.google.com/contrib/1"}]}],
}]}


@pytest.fixture
def net(monkeypatch):
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request):
        calls.append(req)
        u = str(req.url)
        if u.startswith("https://places.googleapis.com/v1/places:searchText"):
            return httpx.Response(200, json=PLACES)
        if u.startswith(f"https://places.googleapis.com/v1/{PHOTO_NAME}/media"):
            return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})
        if u == "https://lotus.example":
            html = ('<html><head><meta property="og:image" content="/img/hero.png"></head>'
                    '<body><img src="https://lotus.example/img/cake.jpg"><img src="/logo.svg"></body></html>')
            return httpx.Response(200, text=html, headers={"content-type": "text/html"})
        if u == "https://lotus.example/img/hero.png":
            return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
        if u == "https://lotus.example/img/cake.jpg":
            return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})
        raise httpx.ConnectError("no route", request=req)

    monkeypatch.setattr(dhttp, "transport", httpx.MockTransport(handler))
    monkeypatch.setattr(website_audit, "guard_target", lambda url: None)
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")
    monkeypatch.setenv("OLLAMA_BASE_URL", "")
    monkeypatch.setattr(ai_config, "http_transport", None)
    return calls


def _acct(client, name="Pipe Org"):
    a = register(client, name)
    return a, tenant_headers(a)


def _google_business(client, h) -> str:
    r = client.post(f"{D}/search", headers=h, json={"criteria": {"source": "google_places", "city": "Pune",
                                                                 "category": "bakery"}})
    assert r.status_code == 201, r.text
    biz = client.get(B, headers=h).json()["items"]
    return next(b["id"] for b in biz if b["name"] == "Lotus Bakery")


def _upload(client, h, bid, data=PNG, permission=True, name="a.png"):
    return client.post(f"{B}/{bid}/images", headers=h, files={"file": (name, data, "image/png")},
                       data={"permission_confirmed": "true" if permission else "false"})


# ------------------------------------------------------------------ Google photos
def test_field_mask_requests_photos_and_refs_stored_with_retention(client, net):
    assert "places.photos" in google_places.FIELD_MASK.split(",")
    a, h = _acct(client)
    bid = _google_business(client, h)
    search = next(c for c in net if "searchText" in str(c.url))
    assert "places.photos" in search.headers["X-Goog-FieldMask"]
    with tenant_session(uuid.UUID(a["org_id"])) as db:
        row = db.scalar(select(BusinessSourceField).where(BusinessSourceField.business_id == uuid.UUID(bid),
                                                          BusinessSourceField.field == "photo"))
        assert row is not None and row.retention_until is not None
        assert json.loads(row.value)["name"] == PHOTO_NAME
    r = client.get(f"{B}/{bid}/google-photos", headers=h)
    assert r.status_code == 200
    ph = r.json()["photos"][0]
    assert ph["attributions"][0]["display_name"] == "Asha K"
    assert ph["usable_in_website"] is False and "not" in ph["notice"].lower()


def test_photo_proxy_returns_attribution_and_never_persists_bytes(client, net):
    a, h = _acct(client)
    bid = _google_business(client, h)
    r = client.get(f"{B}/{bid}/google-photos/media", headers=h, params={"name": PHOTO_NAME, "max_width": 400})
    assert r.status_code == 200 and r.content == JPEG
    assert r.headers["cache-control"] == "private, no-store"
    assert json.loads(unquote(r.headers["x-photo-attribution"]))[0]["display_name"] == "Asha K"
    media = next(c for c in net if "/media" in str(c.url))
    assert media.url.params["maxWidthPx"] == "400" and media.url.params["key"] == "test-key"
    with tenant_session(uuid.UUID(a["org_id"])) as db:
        assert db.scalar(select(func.count()).select_from(BusinessImage)
                         .where(BusinessImage.organization_id == uuid.UUID(a["org_id"]))) == 0
        vals = db.scalars(select(BusinessSourceField.value).where(
            BusinessSourceField.business_id == uuid.UUID(bid))).all()
        assert all(v is None or len(v) < 2000 for v in vals)  # only references, never image bytes
    # a photo name not belonging to this business is refused (no open proxy)
    r = client.get(f"{B}/{bid}/google-photos/media", headers=h, params={"name": "places/x/photos/other123"})
    assert r.status_code == 404


# ------------------------------------------------------------------ business images
def test_owner_image_requires_permission_and_magic_bytes(client, net):
    _, h = _acct(client)
    bid = _google_business(client, h)
    r = _upload(client, h, bid, permission=False)
    assert r.status_code == 422 and r.json()["error"]["code"] == "permission_required"
    r = _upload(client, h, bid, data=b"GIF89a" + b"\x00" * 20, name="x.png")
    assert r.status_code == 415
    r = _upload(client, h, bid, data=b"\xff\xd8\xff" + b"\x00" * (5 * 1024 * 1024 + 10))
    assert r.status_code == 413
    r = _upload(client, h, bid)
    assert r.status_code == 201, r.text
    img = r.json()
    assert img["source"] == "owner_supplied" and img["status"] == "approved" and img["usable_in_website"]


def test_website_import_needs_review_and_generator_uses_only_approved(client, net):
    _, h = _acct(client)
    bid = _google_business(client, h)
    r = client.post(f"{B}/{bid}/images/import-website", headers=h)
    assert r.status_code == 200, r.text
    imported = r.json()["imported"]
    assert len(imported) == 2 and all(i["status"] == "pending_review" for i in imported)
    assert all(i["source"] == "from_business_website" for i in imported)
    pending = imported[0]["id"]
    gen = {"template_key": "general_smb", "business_id": bid, "use_ai": False}
    r = client.post("/api/v1/websites/generate", headers=h, json={**gen, "images": [pending]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "image_not_approved"
    r = client.post(f"{B}/{bid}/images/{pending}/approve", headers=h, json={"permission_confirmed": False})
    assert r.status_code == 422
    r = client.post(f"{B}/{bid}/images/{pending}/approve", headers=h, json={"permission_confirmed": True})
    assert r.status_code == 200 and r.json()["usable_in_website"]
    owner = _upload(client, h, bid).json()["id"]
    r = client.post("/api/v1/websites/generate", headers=h, json={**gen, "images": [pending, owner]})
    assert r.status_code == 201, r.text
    html = r.json()["rendered_html"]
    assert html.count("/api/v1/public/media/") == 2 and "<img" in html
    assert "googleapis" not in html and "googleusercontent" not in html and PHOTO_NAME not in html
    # Google photo names are not images the generator accepts
    r = client.post("/api/v1/websites/generate", headers=h, json={**gen, "images": [PHOTO_NAME]})
    assert r.status_code == 422
    # without images: styled no-photo design
    r = client.post("/api/v1/websites/generate", headers=h, json=gen)
    assert r.status_code == 201 and "/api/v1/public/media/" not in r.json()["rendered_html"]
    # public media serves approved images only
    token_html = html.split("/api/v1/public/media/")[1].split('"')[0]
    assert client.get(f"/api/v1/public/media/{token_html}").status_code == 200


# ------------------------------------------------------------------ extraction
def test_rule_extraction_budget_only_when_stated():
    t = [{"role": "assistant", "text": "Hi, this is an automated AI assistant. What budget do you have?"},
         {"role": "user", "text": "We have a website but it is old. I'm the owner."},
         {"role": "user", "text": "Our budget is between ₹20,000 and ₹40,000. We want it live next month."},
         {"role": "user", "text": "Send me the proposal."}]
    o = extraction.rules_extract(t)
    assert o.extraction_mode == "rules"
    assert (o.budget_min, o.budget_max, o.budget_currency) == (20000, 40000, "INR")
    assert "₹20,000" in o.budget_evidence
    assert o.timeline == "next month" and o.decision_maker == "prospect (self)"
    assert o.interest == "high" and o.next_step == "Send proposal / quote"
    # agent mentioning a price is not the prospect's budget; no stated amount -> null
    t2 = [{"role": "assistant", "text": "Packages start at $500."},
          {"role": "user", "text": "That's too expensive, I need to discuss with my partner. Call me back later."}]
    o2 = extraction.rules_extract(t2)
    assert o2.budget_min is None and o2.budget_max is None and o2.budget_evidence is None
    assert o2.interest == "low" and any(x["objection"] == "price" for x in o2.objections)
    assert o2.decision_maker.startswith("someone else")
    assert extraction.rules_extract([{"role": "user", "text": "Not interested, do not call again."}]).interest == "none"


def test_ollama_json_extraction_path_and_unbacked_budget_dropped(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test")
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        content = {"interest": "medium", "budget_min": 300, "budget_max": 600, "budget_currency": "usd",
                   "budget_evidence": "maybe 300 to 600 dollars", "timeline": "in two weeks",
                   "timeline_evidence": "in two weeks would be nice", "decision_maker": "CEO",
                   "decision_maker_evidence": "invented quote", "objections": [], "next_step": "Send quote",
                   "summary": "Prospect wants a site."}
        return httpx.Response(200, json={"message": {"role": "assistant", "content": json.dumps(content)}})

    monkeypatch.setattr(ai_config, "http_transport", httpx.MockTransport(handler))
    t = [{"role": "user", "text": "We could spend maybe 300 to 600 dollars, in two weeks would be nice."}]
    o = extraction.extract(t)
    assert seen["body"]["format"] == "json" and o.extraction_mode == "llm"
    assert (o.budget_min, o.budget_max, o.budget_currency) == (300, 600, "USD")
    assert o.timeline == "in two weeks" and o.decision_maker is None  # evidence not in transcript -> dropped
    # model claims a budget the prospect never stated -> dropped
    t2 = [{"role": "user", "text": "Sounds good, tell me more."}]
    o2 = extraction.extract(t2)
    assert o2.budget_min is None and "budget_dropped_no_verbatim_evidence" in o2.warnings


def test_outcome_written_to_lead(client, net):
    a, h = _acct(client)
    lead = client.post("/api/v1/leads", headers=h, json={"business_name": "Lotus", "country": "IN"}).json()
    r = client.post(f"{P}/outcomes/extract", headers=h, json={
        "lead_id": lead["id"], "source": "browser_voice",
        "transcript": [{"role": "assistant", "text": "Hello, I'm an AI assistant."},
                       {"role": "user", "text": "Budget is around $800, ideally this month."}]})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["extraction_mode"] == "rules" and out["budget_min"] == 800 and out["budget_currency"] == "USD"
    got = client.get(f"/api/v1/leads/{lead['id']}", headers=h).json()
    lead_obj = got.get("lead", got)
    assert lead_obj["custom_fields"]["budget"]["max"] == 800
    assert lead_obj["custom_fields"]["timeline"] == "this month"
    with tenant_session(uuid.UUID(a["org_id"])) as db:
        from app.modules.crm.models import LeadActivity, LeadNote

        lid = uuid.UUID(lead["id"])
        assert db.scalar(select(LeadActivity).where(LeadActivity.lead_id == lid,
                                                    LeadActivity.type == "conversation.outcome")) is not None
        assert "Budget evidence" in db.scalar(select(LeadNote.body).where(LeadNote.lead_id == lid))
        assert db.scalar(select(func.count()).select_from(ConversationOutcome)
                         .where(ConversationOutcome.lead_id == lid)) == 1


# ------------------------------------------------------------------ budget agent template
def test_budget_agent_template_disclosure_and_packages(client, net):
    _, h = _acct(client)
    r = client.post(f"{P}/budget-agent", headers=h, json={"business_name": "Acme Web"})
    assert r.status_code == 201, r.text
    ag = r.json()
    assert "automated AI assistant" in ag["compliance_disclosure"] and "Acme Web" in ag["compliance_disclosure"]
    assert "Do NOT quote" in ag["business_info"]
    assert client.put(f"{P}/packages", headers=h, json={"packages": [
        {"name": "Starter", "min": 15000, "max": 25000, "currency": "inr"}]}).status_code == 200
    ag2 = client.post(f"{P}/budget-agent", headers=h, json={}).json()
    assert "Starter: INR 15,000–25,000" in ag2["business_info"]


# ------------------------------------------------------------------ pipeline run
def test_pipeline_idempotent_and_call_blocked_with_fixes(client, net):
    _, h = _acct(client)
    bid = _google_business(client, h)
    owner_img = _upload(client, h, bid).json()["id"]
    agent = client.post(f"{P}/budget-agent", headers=h, json={}).json()
    body = {"business_id": bid, "image_ids": [owner_img], "agent_id": agent["id"], "place_call": True}
    r1 = client.post(f"{P}/run", headers=h, json=body)
    assert r1.status_code == 200, r1.text
    run = r1.json()
    steps = {s["key"]: s for s in run["steps"]}
    assert steps["lead"]["status"] == "done" and steps["website"]["status"] == "done"
    assert steps["call"]["status"] == "blocked"
    assert "agent_not_published" in steps["call"]["reasons"] and steps["call"]["fixes"]
    assert run["status"] == "needs_action"
    r2 = client.post(f"{P}/run", headers=h, json=body).json()
    assert r2["id"] == run["id"] and r2["lead_id"] == run["lead_id"]
    assert r2["website_project_id"] == run["website_project_id"]
    s2 = {s["key"]: s for s in r2["steps"]}
    assert s2["lead"]["status"] == "skipped" and s2["website"]["status"] == "skipped"
    assert client.get("/api/v1/websites", headers=h).json()["total"] == 1


def test_cross_tenant_404_and_rbac_403(client, net):
    owner, h = _acct(client, "Pipe Owner")
    bid = _google_business(client, h)
    img = _upload(client, h, bid).json()["id"]
    _, other = _acct(client, "Pipe Other")
    assert client.get(f"{B}/{bid}/google-photos", headers=other).status_code == 404
    assert client.get(f"{B}/{bid}/images/{img}/content", headers=other).status_code == 404
    assert client.post(f"{P}/run", headers=other, json={"business_id": bid}).status_code == 404
    gen = {"template_key": "general_smb", "business": {"name": "X"}, "use_ai": False, "images": [img]}
    assert client.post("/api/v1/websites/generate", headers=other, json=gen).status_code == 404
    viewer_acct = register(client, "Viewer Org")
    r = client.post(f"/api/v1/organizations/{owner['org_id']}/members", headers=owner["headers"],
                    json={"email": viewer_acct["email"], "role": "Viewer"})
    assert r.status_code == 201
    viewer = tenant_headers(viewer_acct, owner["org_id"])
    assert client.get(f"{B}/{bid}/images", headers=viewer).status_code == 200
    assert _upload(client, viewer, bid).status_code == 403
    assert client.post(f"{P}/run", headers=viewer, json={"business_id": bid}).status_code == 403
    assert client.post(f"{B}/{bid}/images/{img}/approve", headers=viewer,
                       json={"permission_confirmed": True}).status_code == 403


def test_llm_paraphrase_is_backfilled_only_from_stated_facts(monkeypatch):
    """A small model that paraphrases (no verbatim quote) must not lose stated facts, and must not invent any."""
    from app.modules.pipeline import extraction as ex

    def fake_llm(transcript, model=None):
        o = ex.Outcome(extraction_mode="llm", model="tiny")
        o.interest = "high"
        o.warnings.append("budget_dropped_no_verbatim_evidence")
        return o

    monkeypatch.setattr(ex, "llm_extract", fake_llm)
    stated = [{"role": "contact",
               "text": "Our budget is around 20,000 to 30,000 rupees and we want it live next month."}]
    o = ex.extract(stated)
    assert (o.budget_min, o.budget_max, o.budget_currency) == (20000.0, 30000.0, "INR")
    assert o.budget_evidence and "20,000" in o.budget_evidence
    assert any(w.startswith("backfilled_by_rules") for w in o.warnings)
    silent = [{"role": "contact", "text": "Sounds interesting, send me details."}]
    o2 = ex.extract(silent)
    assert o2.budget_min is None and o2.budget_max is None and o2.timeline is None
