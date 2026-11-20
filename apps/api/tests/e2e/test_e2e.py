"""Live-stack end-to-end suite (Playwright, Chromium) — drives the product like a real user.

Runs against the Docker stack (web :3010, api :8010). Each run registers a brand-new organization through the
UI, so it never touches existing tenants. Excluded from the default unit run (see pyproject `norecursedirs`);
run explicitly:

    PLAYWRIGHT_BROWSERS_PATH=D:/tmp/pw-browsers python -m pytest tests/e2e -q

Tests are ordered steps sharing one browser session (module-scoped state); a failing step skips the rest.
Screenshots of every step land in E2E_SHOTS (default D:/tmp/pw/qa).
"""
import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

WEB = os.environ.get("E2E_WEB", "http://localhost:3010")
API = os.environ.get("E2E_API", "http://localhost:8010") + "/api/v1"
SHOTS = Path(os.environ.get("E2E_SHOTS", "D:/tmp/pw/qa"))
CSV = Path(__file__).resolve().parents[4] / "database" / "seeds" / "sample_businesses.csv"
PASSWORD = "E2eTestPass2026"


def _reachable(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=5)  # noqa: S310 - fixed local URL
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


playwright_api = pytest.importorskip("playwright.sync_api")
pytestmark = [pytest.mark.e2e,
              pytest.mark.skipif(not _reachable(WEB), reason=f"live stack not reachable at {WEB}")]


def call(method, path, token=None, org=None, body=None):
    req = urllib.request.Request(API + path, method=method,  # noqa: S310 - fixed local URL
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if org:
        req.add_header("X-Organization-Id", org)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:  # noqa: S310
            raw = r.read()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw.decode(errors="replace")}


class S:
    """Shared run state."""
    run = uuid.uuid4().hex[:8]
    email = f"e2e-owner-{run}@example.com"
    mgr_email = f"e2e-manager-{run}@example.com"
    org_name = f"E2E Org {run}"
    failed = False
    errors: list = []


@pytest.fixture(scope="module")
def browser():
    with playwright_api.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture(scope="module")
def page(browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.set_default_timeout(20000)
    pg.on("pageerror", lambda e: S.errors.append(f"PAGEERROR {pg.url}: {e}"))
    pg.on("console", lambda m: S.errors.append(f"{pg.url}: console {m.text}")
          if m.type == "error" and "Failed to load resource" not in m.text else None)
    yield pg
    ctx.close()


def shot(pg, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    pg.wait_for_timeout(600)
    pg.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)


def go(pg, path):
    pg.goto(WEB + path, wait_until="networkidle")
    pg.wait_for_timeout(800)


def api(pg, method, path, body=None):
    token = pg.evaluate("localStorage.getItem('lx_access')")
    org = pg.evaluate("localStorage.getItem('lx_org')")
    return call(method, path, token, org, body)


def dialog(pg, title):
    d = pg.get_by_role("dialog", name=title)
    d.wait_for()
    return d


def no_error_alert(pg):
    alerts = pg.locator("[role=alert]:not(#__next-route-announcer__)").all_inner_texts()
    assert not [a for a in alerts if a.strip()], f"error alert on {pg.url}: {alerts}"


# ---------------------------------------------------------------------------------------------- steps

def test_01_register(page):
    go(page, "/register")
    page.fill("#full_name", "E2E Owner")
    page.fill("#email", S.email)
    page.fill("#password", PASSWORD)
    page.fill("#org", S.org_name)
    page.fill("#cc", "IN")
    shot(page, "01_register")
    page.get_by_role("button", name="Create account").click()
    page.wait_for_url("**/dashboard", timeout=30000)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)
    shot(page, "02_dashboard")
    assert S.org_name in page.content()


def test_02_discovery_csv_import(page):
    go(page, "/discovery")
    page.locator("input[type=file]").set_input_files(str(CSV))
    page.get_by_text("Fictional Crumb & Co Bakery").first.wait_for(timeout=30000)
    shot(page, "03_discovery_imported")
    s, res = api(page, "GET", "/businesses?page_size=100")
    assert s == 200
    items = res["items"]
    assert len(items) >= 25
    by_name = {b["name"]: b for b in items}
    assert by_name["Thames Pretend Bakehouse"]["country"] == "GB"
    assert by_name["Mirage Test Bakery Dubai"]["country"] == "AE"
    S.business = by_name["Placeholder Arches Architects"]
    S.business2 = by_name["Demo Builders & Developers"]


def test_03_businesses_search(page):
    go(page, "/discovery")
    page.get_by_placeholder("Search name, city, domain").fill("Hyderabad")
    page.wait_for_timeout(1500)
    shot(page, "04_businesses_search")
    assert page.get_by_text("Fictitious Biryani House").count() >= 1
    assert page.get_by_text("Thames Pretend Bakehouse").count() == 0


def test_04_business_detail_audit_and_convert(page):
    go(page, f"/businesses/{S.business['id']}")
    page.get_by_text("Placeholder Arches Architects").first.wait_for()
    page.get_by_role("button", name="Run audit").click()
    page.wait_for_timeout(8000)
    shot(page, "05_business_detail_audit")
    # example.com sites may fail to audit; the page must stay usable (no crash).
    assert page.get_by_text("Application error").count() == 0
    page.get_by_role("button", name="Convert to lead").click()
    page.get_by_text("Already in leads").wait_for()
    s, b = api(page, "GET", f"/businesses/{S.business['id']}")
    b = b["business"]
    assert s == 200 and b.get("lead_id"), b
    S.lead_id = b["lead_id"]
    shot(page, "06_business_converted")


def test_05_leads_list_filters(page):
    s, _ = api(page, "POST", f"/businesses/{S.business2['id']}/convert-to-lead")
    assert s == 201
    go(page, "/leads")
    page.get_by_text("Demo Builders & Developers").first.wait_for()
    page.get_by_label("Search leads").fill("Arches")
    page.wait_for_timeout(1500)
    assert page.get_by_text("Placeholder Arches Architects").count() >= 1
    assert page.get_by_text("Demo Builders & Developers").count() == 0
    page.get_by_role("button", name="Discovered", exact=True).click()
    page.wait_for_timeout(1200)
    assert page.get_by_text("Placeholder Arches Architects").count() >= 1
    shot(page, "07_leads_filtered")
    page.get_by_role("button", name="Verified", exact=True).click()  # discovered OR verified -> still shown
    page.wait_for_timeout(1000)
    page.get_by_text("Clear filters").click()
    page.wait_for_timeout(1200)
    assert page.get_by_text("Demo Builders & Developers").count() >= 1


def test_06_lead_detail_edit_note_task(page):
    go(page, f"/leads/{S.lead_id}")
    page.get_by_role("heading", name="Placeholder Arches Architects").wait_for()
    page.get_by_role("button", name="Edit").click()
    d = dialog(page, "Edit lead")
    d.locator("#e-score").fill("72")
    d.locator("#e-city").fill("Pune")
    d.get_by_role("button", name="Save changes").click()
    d.wait_for(state="hidden")
    assert page.get_by_text("72", exact=True).count() >= 1
    page.get_by_role("tab", name="Notes").click()
    page.get_by_placeholder("Write a note…").fill("E2E: owner prefers WhatsApp after 6pm.")
    page.get_by_role("button", name="Add note").click()
    page.get_by_text("E2E: owner prefers WhatsApp after 6pm.").wait_for()
    page.get_by_role("tab", name="Tasks").click()
    page.locator("#t-title").fill("E2E follow-up call")
    page.locator("#t-title").press("Enter")
    page.get_by_text("E2E follow-up call").first.wait_for()
    shot(page, "08_lead_note_task")


def test_07_lead_status_consent_approval(page):
    page.get_by_role("button", name="Change status").click()
    d = dialog(page, "Change status")
    d.get_by_role("button", name="Verified", exact=True).click()
    d.get_by_role("button", name="Update status").click()
    d.wait_for(state="hidden")
    page.get_by_text("Verified").first.wait_for()
    page.get_by_role("button", name="Add consent").click()
    d = dialog(page, "Add consent")
    d.locator("select").nth(1).select_option("written_consent")
    d.get_by_placeholder("e.g. Signed form on 2026-11-01").fill("E2E signed consent form #E2E-1")
    d.get_by_role("button", name="Save consent").click()
    d.wait_for(state="hidden")
    page.get_by_role("button", name="Change status").click()
    d = dialog(page, "Change status")
    d.get_by_role("button", name="Approved for outreach", exact=True).click()
    d.locator("#consent").fill("E2E-CONSENT-1")
    shot(page, "09_status_dialog_consent")
    d.get_by_role("button", name="Update status").click()
    d.wait_for(state="hidden")
    page.get_by_text("Consent on file").wait_for()
    page.get_by_role("tab", name="Activity").click()
    shot(page, "10_lead_approved")
    s, lead = api(page, "GET", f"/leads/{S.lead_id}")
    assert lead["status"] == "approved_for_outreach" and lead["consent_reference"] == "E2E-CONSENT-1"


def test_08_website_generate_and_edit(page):
    go(page, f"/leads/{S.lead_id}")
    page.get_by_role("button", name="Generate website").click()
    d = dialog(page, "Generate website")
    d.get_by_role("button", name="Generate").click()
    d.get_by_role("link", name="Open in Website Studio").click(timeout=120000)
    page.wait_for_url("**/websites/*")
    S.site_id = page.url.rstrip("/").split("/")[-1]
    frame = page.frame_locator("iframe[title='Website preview']")
    frame.locator("body").get_by_text("Placeholder Arches Architects").first.wait_for(timeout=30000)
    shot(page, "11_website_studio")
    page.get_by_placeholder("Heading").first.fill("E2E Edited Hero Heading")
    frame.get_by_text("E2E Edited Hero Heading").first.wait_for(timeout=15000)
    page.get_by_placeholder("Version note (optional)").fill("e2e edit")
    page.get_by_role("button", name="Save as new version").click()
    page.get_by_role("button", name="Saved").wait_for()
    assert page.get_by_text("v2").count() >= 1
    shot(page, "12_website_saved_v2")


def test_09_website_share_approve_publish(page, browser):
    page.get_by_role("button", name="Share preview").click()
    share = page.locator("code").first
    share.wait_for()
    url = share.inner_text().strip()
    anon = browser.new_context()
    try:
        pub = anon.new_page()
        r = pub.goto(url, wait_until="networkidle")
        assert r.status == 200, url
        assert "E2E Edited Hero Heading" in pub.content()
        shot(pub, "13_public_preview_link")
        page.once("dialog", lambda dl: dl.accept())
        page.get_by_role("button", name="Approve").click()
        page.get_by_text("approved", exact=True).wait_for()
        page.once("dialog", lambda dl: dl.accept())
        page.get_by_role("button", name="Publish").click()
        live = page.get_by_text("Live (local hosting):").locator("a")
        live.wait_for(timeout=60000)
        live_url = live.get_attribute("href")
        shot(page, "14_website_published")
        r = pub.goto(live_url, wait_until="networkidle")
        assert r.status == 200, live_url
        assert "E2E Edited Hero Heading" in pub.content()
        shot(pub, "15_public_site")
    finally:
        anon.close()


def test_10_pipeline_run(page):
    go(page, "/pipeline")
    page.get_by_label("Search businesses").fill("Demo Builders")
    page.get_by_role("main").get_by_role("button", name="Search", exact=True).click()
    page.get_by_role("button", name="Demo Builders & Developers").first.click()
    page.get_by_role("button", name="Run pipeline (lead + website)").click()
    page.get_by_text("4. Status & results").wait_for(timeout=120000)
    shot(page, "16_pipeline_run")
    assert page.get_by_text("Application error").count() == 0


def test_11_agent_template_publish_chat(page):
    go(page, "/agents")
    page.get_by_role("button", name="Use template").first.click()
    page.wait_for_url("**/agents/*")
    page.get_by_role("button", name="Publish").wait_for()
    S.agent_id = page.url.rstrip("/").split("/")[-1]
    page.get_by_role("button", name="Publish").click()
    page.get_by_text("Live version v1").wait_for(timeout=30000)
    shot(page, "17_agent_published")
    go(page, f"/agents/{S.agent_id}/test")
    page.locator("#t-prov").select_option("simulated")
    page.get_by_label("Message").fill(
        "Hi, we run a small bakery in Pune with no website. Budget is about 25,000 rupees, want it next month.")
    page.get_by_role("button", name="Send").click()
    page.get_by_text("Running…").wait_for(state="hidden", timeout=60000)
    no_error_alert(page)
    assert page.locator(".whitespace-pre-wrap").count() >= 1
    page.get_by_role("button", name="End conversation & extract outcome").click()
    page.get_by_text("Conversation outcome").wait_for(timeout=240000)  # extraction may use the local LLM
    shot(page, "18_agent_test_lab_outcome")
    no_error_alert(page)


def test_12_settings_add_manager(page):
    s, _ = call("POST", "/auth/register", body={"full_name": "E2E Manager", "email": S.mgr_email, "password": PASSWORD,
                                                 "organization_name": f"E2E Manager Personal {S.run}"})
    assert s == 201
    go(page, "/settings")
    page.locator("#m-email").fill(S.mgr_email)
    page.locator("#m-role").select_option("Manager")
    page.get_by_role("button", name="Add member").click()
    page.get_by_text(S.mgr_email).wait_for()
    shot(page, "19_settings_members")


def test_13_campaign_create_submit_approve(page, browser):
    s, _ = api(page, "POST", "/email/templates", {"name": "E2E intro", "subject": "Hello {{business_name}}",
                                                  "html": "<p>Hi {{business_name}}, we built you a demo site.</p>"})
    assert s == 201
    go(page, "/campaigns/new")
    page.get_by_label("Name").fill(f"E2E campaign {S.run}")
    page.get_by_role("button", name="Continue").click()
    page.get_by_role("button", name="Add step").click()
    page.get_by_label("Physical mailing address (required by CAN-SPAM)").fill("1 Fictional Road, Pune 411001, India")
    page.get_by_role("button", name="Continue").click()
    page.locator("textarea").fill(S.lead_id)
    page.get_by_role("button", name="Continue").click()
    shot(page, "20_campaign_review")
    page.get_by_role("button", name="Create draft").click()
    page.wait_for_url("**/campaigns/*-*")
    S.campaign_url = page.url
    page.get_by_role("button", name="Submit for approval").click()
    page.get_by_text("pending approval").first.wait_for()
    approve = page.get_by_role("button", name="Approve", exact=True)
    if approve.count():
        approve.click()
        page.get_by_text("A different member must approve this campaign").wait_for()
    shot(page, "21_campaign_submitted_self_approval_blocked")
    org_id = page.evaluate("localStorage.getItem('lx_org')")
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    try:
        mp = ctx.new_page()
        mp.goto(WEB + "/login", wait_until="networkidle")
        mp.fill("#email", S.mgr_email)
        mp.fill("#password", PASSWORD)
        mp.keyboard.press("Enter")
        mp.wait_for_url("**/dashboard", timeout=30000)
        mp.wait_for_load_state("networkidle")
        mp.wait_for_timeout(1500)
        assert mp.evaluate("localStorage.getItem('lx_access')"), "manager token missing after login"
        mp.evaluate(f"localStorage.setItem('lx_org', '{org_id}')")
        mp.goto(S.campaign_url, wait_until="networkidle")
        try:
            mp.get_by_role("button", name="Approve", exact=True).click()
        except Exception:
            shot(mp, "FAIL_manager_view")
            raise
        mp.get_by_text("approved", exact=True).first.wait_for()
        shot(mp, "22_campaign_approved_by_manager")
    finally:
        ctx.close()


def test_14_campaigns_list(page):
    go(page, "/campaigns")
    page.get_by_text(f"E2E campaign {S.run}").wait_for()
    shot(page, "23_campaigns_list")


def test_15_compliance_suppression_and_gate(page):
    go(page, "/compliance")
    page.get_by_role("tab", name="Suppressions").click()
    page.locator("#s-em").fill(f"optout-{S.run}@example.com")
    page.locator("#s-r").fill("E2E: asked not to be contacted")
    page.get_by_role("button", name="Suppress").click()
    page.get_by_text(f"optout-{S.run}@example.com").first.wait_for()
    shot(page, "24_compliance_suppression")
    page.get_by_role("tab", name="Gate checker").click()
    page.locator("#g-lead").select_option(S.lead_id)
    page.locator("#g-ch").select_option("email")
    page.get_by_role("button", name="Check").click()
    page.wait_for_timeout(2500)
    no_error_alert(page)
    shot(page, "25_compliance_gate")
    assert page.get_by_text("allowed", exact=False).count() + page.get_by_text("blocked", exact=False).count() >= 1


def test_16_marketplace_requirement_provider_match_referral(page):
    go(page, "/marketplace")
    s, cats = api(page, "GET", "/marketplace/categories")
    assert s == 200 and cats, "no marketplace categories seeded"
    cat = cats[0]
    page.get_by_role("button", name="Providers").click()
    page.get_by_role("button", name="New provider").click()
    page.get_by_label("Business name").fill(f"E2E Fictional Web Studio {S.run}")
    page.get_by_label("Service city").fill("Pune")
    page.get_by_label("Service country (ISO-2)").fill("IN")
    page.get_by_role("button", name=cat["name"], exact=True).click()
    page.get_by_role("button", name="Save provider").click()
    page.get_by_text(f"E2E Fictional Web Studio {S.run}").wait_for()
    shot(page, "26_marketplace_provider")
    page.get_by_role("button", name="Requirements").click()
    page.get_by_role("button", name="New requirement").click()
    page.get_by_label("Customer name").fill("Fictional Customer")
    page.get_by_label("Customer email").fill(f"customer-{S.run}@example.com")
    page.get_by_label("Service category").select_option(cat["id"])
    page.get_by_label("Title").fill("E2E need a bakery website")
    page.get_by_label("City").fill("Pune")
    page.get_by_label("Country (ISO-2)").fill("IN")
    page.get_by_text("Customer has given permission").click()
    page.get_by_label("Consent reference (required)").fill("E2E-MKT-CONSENT")
    page.get_by_role("button", name="Save requirement").click()
    page.get_by_text("E2E need a bakery website").wait_for()
    page.get_by_role("button", name="Run matching").click()
    page.get_by_role("button", name="Refer").first.click(timeout=30000)
    page.get_by_text("Referral created.").wait_for()
    shot(page, "27_marketplace_match_referral")
    go(page, "/referrals")
    page.get_by_text("E2E need a bakery website").first.wait_for()
    shot(page, "28_referrals")


def test_17_commissions(page):
    go(page, "/commissions")
    page.get_by_role("heading", name="Commissions").wait_for()
    no_error_alert(page)
    shot(page, "29_commissions")


def test_18_workflow_build_run(page):
    go(page, "/workflows")
    page.get_by_placeholder("New workflow name").fill(f"E2E manual flow {S.run}")
    page.get_by_role("button", name="Create").click()
    page.wait_for_url("**/workflows/*-*")
    wid = page.url.rstrip("/").split("/")[-1]
    graph = {"nodes": [{"id": "t", "type": "trigger", "config": {}},
                       {"id": "n", "type": "notification", "config": {"message": "E2E hello"}}],
             "edges": [{"source": "t", "target": "n"}]}
    s, _ = api(page, "PATCH", f"/workflows/{wid}", {"graph": graph})
    assert s == 200
    page.reload(wait_until="networkidle")
    page.get_by_role("button", name="Validate").click()
    page.get_by_text("Graph is valid").wait_for()
    page.get_by_role("button", name="Save version").click()
    page.get_by_text("Published version 1").wait_for()
    page.get_by_role("button", name="Run published version").click()
    for _ in range(40):  # the background worker executes the run
        _, ex = api(page, "GET", f"/workflows/{wid}/executions")
        if ex["items"] and ex["items"][0]["status"] not in ("queued", "running"):
            break
        page.wait_for_timeout(1000)
    assert ex["items"][0]["status"] == "succeeded", ex["items"][0]
    page.reload(wait_until="networkidle")
    page.get_by_text("succeeded", exact=True).first.click()
    page.get_by_text("Execution log").wait_for()
    assert page.locator("ol.font-mono li").count() >= 2
    shot(page, "30_workflow_run")


def test_19_billing(page):
    go(page, "/billing")
    page.get_by_text("Usage ·").wait_for()
    no_error_alert(page)
    shot(page, "31_billing")


def test_20_settings_security(page):
    go(page, "/settings/security")
    page.get_by_role("button", name="Set up authenticator").click()
    page.get_by_text("Setup key", exact=True).wait_for()
    shot(page, "32_security_mfa_setup")  # not enabled: no code is submitted


MOBILE_ROUTES = ["/dashboard", "/discovery", "/leads", "/leads/{lead}", "/websites", "/websites/{site}", "/pipeline",
                 "/agents", "/campaigns", "/compliance", "/marketplace", "/commissions", "/workflows", "/billing",
                 "/settings", "/settings/security"]


def test_21_mobile_390_no_horizontal_overflow(browser, page):
    state = page.context.storage_state()
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, storage_state=state, is_mobile=True,
                              has_touch=True)
    origin_ls = {"lx_access": page.evaluate("localStorage.getItem('lx_access')"),
                 "lx_refresh": page.evaluate("localStorage.getItem('lx_refresh')"),
                 "lx_org": page.evaluate("localStorage.getItem('lx_org')")}
    ctx.add_init_script("".join(f"localStorage.setItem('{k}', {json.dumps(v)});" for k, v in origin_ls.items() if v))
    overflow = []
    try:
        mp = ctx.new_page()
        for r in MOBILE_ROUTES:
            path = r.format(lead=S.lead_id, site=getattr(S, "site_id", ""))
            mp.goto(WEB + path, wait_until="networkidle")
            mp.wait_for_timeout(1200)
            sw = mp.evaluate("document.documentElement.scrollWidth")
            name = "m_" + (path.strip("/").replace("/", "_")[:40] or "root")
            shot(mp, name)
            if sw > 392:
                overflow.append(f"{path}: scrollWidth={sw}")
    finally:
        ctx.close()
    assert not overflow, overflow


def test_22_logout(page):
    go(page, "/dashboard")
    page.get_by_role("button", name="Account menu").click()
    page.get_by_role("button", name="Sign out").click()
    page.wait_for_url("**/login")
    shot(page, "33_logged_out")
    assert page.evaluate("localStorage.getItem('lx_access')") is None


def test_99_no_uncaught_page_errors():
    console = [e for e in S.errors if not e.startswith("PAGEERROR")]
    if console:
        print("browser console errors:", *console[:20], sep="\n  ")
    errs = [e for e in S.errors if e.startswith("PAGEERROR")]
    assert not errs, errs[:10]
