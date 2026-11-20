import json
import re

from tests.conftest import register, tenant_headers

W = "/api/v1/websites"
BIZ = {"name": "Sunrise Dental", "industry": "Dental clinic", "city": "Pune", "phone": "+91 98765 43210",
       "email": "hello@sunrise.example", "services": ["Cleaning", "Braces"],
       "description": "Family dental care."}


def _gen(client, h, template="clinic", **biz):
    r = client.post(f"{W}/generate", headers=h, json={"template_key": template, "business": {**BIZ, **biz}})
    assert r.status_code == 201, r.text
    return r.json()


def _add_member(client, owner, other, role):
    r = client.post(f"/api/v1/organizations/{owner['org_id']}/members", headers=owner["headers"],
                    json={"email": other["email"], "role": role})
    assert r.status_code == 201, r.text


def test_templates_catalogue(client):
    a = register(client, "Web Tpl")
    r = client.get(f"{W}/templates", headers=tenant_headers(a))
    assert r.status_code == 200
    keys = [t["key"] for t in r.json()]
    assert len(keys) == 11 and {"real_estate", "restaurant", "general_smb", "professional_services"} <= set(keys)
    assert len({json.dumps(t["theme"], sort_keys=True) for t in r.json()}) == 11  # distinct designs


def test_generate_renders_only_supplied_facts(client):
    a = register(client, "Web Gen")
    p = _gen(client, tenant_headers(a), whatsapp_number="+91 99999 88888")
    assert p["status"] == "draft" and p["current_version_number"] == 1 and p["generation_mode"] == "template"
    html = p["rendered_html"]
    assert "Sunrise Dental" in html and 'href="tel:+919876543210"' in html
    assert "wa.me" not in html  # WhatsApp not authorised
    assert "[Add your description of this service]" in html  # missing info marked, not invented
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html).group(1))
    assert ld["@type"] == "LocalBusiness" and ld["telephone"] and "aggregateRating" not in ld
    for banned in ("testimonial", "rating", "award", "certified"):
        assert banned not in html.lower()
    p2 = _gen(client, tenant_headers(a), template="restaurant", whatsapp_number="+91 99999 88888",
              whatsapp_authorized=True)
    assert "https://wa.me/919999988888" in p2["rendered_html"]
    # Lead-based generation
    lead = client.post("/api/v1/leads", headers=tenant_headers(a),
                       json={"business_name": "Lead Bakery", "city": "Goa"}).json()
    r = client.post(f"{W}/generate", headers=tenant_headers(a), json={"template_key": "retail", "lead_id": lead["id"]})
    assert r.status_code == 201 and "Lead Bakery" in r.json()["rendered_html"]
    assert client.post(f"{W}/generate", headers=tenant_headers(a),
                       json={"template_key": "nope", "business": BIZ}).status_code == 422


def test_xss_is_escaped(client):
    a = register(client, "Web XSS")
    h = tenant_headers(a)
    evil = '<script>alert(1)</script>"><img src=x onerror=alert(2)>'
    p = _gen(client, h, name=evil, description=evil, city="</script><script>alert(3)</script>",
             phone="javascript:alert(1)", services=[evil])
    html = p["rendered_html"]
    assert "<script>alert" not in html and "<img src=x" not in html and "javascript:" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    # Editing content goes through the same escaping, including the JSON-LD block.
    content = p["content"]
    content["sections"][0]["heading"] = "</h1><svg onload=alert(4)>"
    content["seo"]["title"] = "</title><script>x()</script>"
    r = client.patch(f"{W}/{p['id']}", headers=h, json={"content": content})
    html = r.json()["rendered_html"]
    assert "<svg onload" not in html and "<script>x()" not in html
    assert len(re.findall(r"<script", html)) == 1  # only the JSON-LD block
    preview = client.get(f"/api/v1/public/preview/{_link(client, h, p['id'])}")
    assert "<svg onload" not in preview.text


def _link(client, h, pid, **kw):
    r = client.post(f"{W}/{pid}/preview-link", headers=h, json=kw)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_versioning_and_restore(client):
    a = register(client, "Web Versions")
    h = tenant_headers(a)
    p = _gen(client, h)
    content = p["content"]
    content["sections"][0]["body"] = "Gentle dentistry for the whole family."
    r = client.patch(f"{W}/{p['id']}", headers=h, json={"content": content, "note": "hero copy"})
    assert r.status_code == 200 and r.json()["current_version_number"] == 2
    assert client.patch(f"{W}/{p['id']}", headers=h, json={"template_key": "corporate"}).json()[
        "current_version_number"] == 3
    vs = client.get(f"{W}/{p['id']}/versions", headers=h).json()
    assert [v["number"] for v in vs] == [3, 2, 1] and vs[1]["note"] == "hero copy"
    v1 = client.get(f"{W}/{p['id']}/versions/{vs[2]['id']}", headers=h).json()
    assert "Gentle dentistry" not in v1["rendered_html"]  # old versions immutable
    r = client.post(f"{W}/{p['id']}/versions/{vs[2]['id']}/restore", headers=h)
    assert r.json()["current_version_number"] == 4 and "Gentle dentistry" not in r.json()["rendered_html"]
    bad = client.patch(f"{W}/{p['id']}", headers=h, json={"content": {"business": {"name": "x"},
                                                                       "sections": [{"type": "iframe"}]}})
    assert bad.status_code == 422
    r = client.post(f"{W}/{p['id']}/render", headers=h, json={"content": content})
    assert r.status_code == 200 and "Gentle dentistry" in r.text and "noindex" in r.text


def test_preview_feedback_publish_rollback(client):
    a = register(client, "Web Publish")
    h = tenant_headers(a)
    p = _gen(client, h)
    pid = p["id"]
    token = _link(client, h, pid)
    r = client.get(f"/api/v1/public/preview/{token}")
    assert r.status_code == 200 and r.headers["x-robots-tag"].startswith("noindex") and "Sunrise Dental" in r.text
    assert client.get("/api/v1/public/preview/not-a-real-token-123").status_code == 404
    r = client.post(f"/api/v1/public/preview/{token}/feedback", json={"name": "<b>Asha</b>", "message": "Looks great",
                                                                     "approved": True})
    assert r.status_code == 201
    fb = client.get(f"{W}/{pid}/feedback", headers=h).json()
    assert fb[0]["approved"] is True and fb[0]["name"] == "<b>Asha</b>"  # stored raw, JSON API, never rendered as HTML

    assert client.post(f"{W}/{pid}/publish", headers=h).status_code == 409  # not approved
    assert client.get(f"/api/v1/sites/{pid}").status_code == 404
    assert client.post(f"{W}/{pid}/approve", headers=h).json()["status"] == "approved"
    d1 = client.post(f"{W}/{pid}/publish", headers=h)
    assert d1.status_code == 200 and d1.json()["target"] == "local"
    v1 = client.get(f"{W}/{pid}", headers=h).json()["published_version_id"]
    site = client.get(f"/api/v1/sites/{pid}")
    assert site.status_code == 200 and "noindex" not in site.text

    content = client.get(f"{W}/{pid}", headers=h).json()["content"]
    content["sections"][0]["body"] = "Version two hero"
    edited = client.patch(f"{W}/{pid}", headers=h, json={"content": content}).json()
    assert edited["status"] == "published" and edited["approved_version_id"] is None
    assert client.post(f"{W}/{pid}/publish", headers=h).status_code == 409  # edit needs re-approval
    client.post(f"{W}/{pid}/approve", headers=h)
    assert client.post(f"{W}/{pid}/publish", headers=h).status_code == 200
    assert "Version two hero" in client.get(f"/api/v1/sites/{pid}").text

    unpublished = client.get(f"{W}/{pid}/versions", headers=h).json()[0]["id"]
    r = client.post(f"{W}/{pid}/rollback", headers=h, json={"version_id": v1})
    assert r.status_code == 200 and r.json()["rolled_back_from"] is not None
    assert "Version two hero" not in client.get(f"/api/v1/sites/{pid}").text
    deps = client.get(f"{W}/{pid}/deployments", headers=h).json()
    assert [d["status"] for d in deps].count("live") == 1
    # rollback target must have been published before; rotating the preview link revokes the old one
    client.patch(f"{W}/{pid}", headers=h, json={"content": content})
    newest = client.get(f"{W}/{pid}/versions", headers=h).json()[0]["id"]
    assert newest != unpublished
    assert client.post(f"{W}/{pid}/rollback", headers=h, json={"version_id": newest}).status_code == 409
    new_token = _link(client, h, pid, rotate=True)
    assert new_token != token and client.get(f"/api/v1/public/preview/{token}").status_code == 404


def test_cross_tenant_404(client):
    a, b = register(client, "Web A"), register(client, "Web B")
    p = _gen(client, tenant_headers(a))
    hb = tenant_headers(b)
    for method, path, body in (("get", f"{W}/{p['id']}", None), ("patch", f"{W}/{p['id']}", {"name": "x"}),
                               ("get", f"{W}/{p['id']}/versions", None), ("post", f"{W}/{p['id']}/approve", None),
                               ("post", f"{W}/{p['id']}/preview-link", {}), ("get", f"{W}/{p['id']}/feedback", None)):
        kw = {"json": body} if body is not None else {}
        assert getattr(client, method)(path, headers=hb, **kw).status_code == 404
    assert client.get(W, headers=hb).json()["total"] == 0
    lead = client.post("/api/v1/leads", headers=tenant_headers(a), json={"business_name": "A Lead"}).json()
    r = client.post(f"{W}/generate", headers=hb, json={"template_key": "retail", "lead_id": lead["id"]})
    assert r.status_code == 404


def test_rbac(client):
    owner, rep, mgr = register(client, "Web RBAC"), register(client, "Rep Home"), register(client, "Mgr Home")
    _add_member(client, owner, rep, "Sales Rep")
    _add_member(client, owner, mgr, "Manager")
    p = _gen(client, tenant_headers(owner))
    hr, hm = tenant_headers(rep, owner["org_id"]), tenant_headers(mgr, owner["org_id"])
    assert client.get(W, headers=hr).status_code == 403
    assert client.post(f"{W}/generate", headers=hr, json={"template_key": "clinic", "business": BIZ}).status_code == 403
    assert client.get(f"{W}/{p['id']}", headers=hm).status_code == 200
    assert client.post(f"{W}/{p['id']}/approve", headers=hm).status_code == 403
    assert client.post(f"{W}/{p['id']}/publish", headers=hm).status_code == 403
    r = client.post(f"{W}/{p['id']}/rollback", headers=hm, json={"version_id": p["current_version_id"]})
    assert r.status_code == 403
