"""Investor demo workspace: a SEPARATE organization filled with clearly-labelled FICTIONAL sample data.

Rules:
- Demo rows only ever go into the new demo organization (never into a real tenant), so analytics of real
  organizations are unaffected.
- Every generated record carries a demo marker where the schema allows it (source="demo", is_simulated=True,
  simulated=True, example.com/example.org contact details, "(Demo)" provider names).
- Company names are invented; phone numbers use reserved/fictional ranges; e-mails use example.com (RFC 2606).
"""
import logging
import random
import secrets
import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.db import Base, set_tenant, utcnow
from app.modules.agents.models import AgentRun, AIAgent
from app.modules.automation.models import Workflow, WorkflowExecution, WorkflowVersion
from app.modules.campaigns.models import Campaign
from app.modules.crm import service as crm
from app.modules.crm.models import Lead, LeadActivity, LeadNote, LeadTask
from app.modules.demo.models import DemoWorkspace
from app.modules.discovery.models import Business
from app.modules.identity.models import Organization, OrganizationMembership, User
from app.modules.identity.router import create_organization
from app.modules.marketplace.models import (
    Customer,
    CustomerRequirement,
    Referral,
    ServiceCategory,
    ServiceProvider,
)
from app.modules.pipeline.models import ConversationOutcome
from app.modules.websites.copywriter import build_content
from app.modules.websites.models import WebsiteProject
from app.modules.websites.router import _new_version, _template

log = logging.getLogger(__name__)
DEMO_NAME = "Demo workspace (fictional data)"

# Fictional businesses: (name, industry, city, country, has_website)
COMPANIES = [
    ("Northwind Dental Studio", "healthcare", "Pune", "IN", False),
    ("Bluepeak Realty Partners", "real_estate", "Bengaluru", "IN", True),
    ("Saffron Lane Bistro", "restaurant", "Mumbai", "IN", False),
    ("Copperleaf Interiors", "interior_design", "Pune", "IN", True),
    ("Harborview Physiotherapy", "healthcare", "Austin", "US", False),
    ("Granite & Beam Builders", "construction", "Hyderabad", "IN", False),
    ("Lumen Learning Academy", "education", "Bengaluru", "IN", True),
    ("Oakridge Legal Associates", "professional_services", "Austin", "US", True),
    ("Tidewater Home Services", "construction", "Mumbai", "IN", False),
    ("Fernhill Boutique", "retail", "Pune", "IN", False),
    ("Quartz Architecture Lab", "architecture", "Hyderabad", "IN", True),
    ("Marigold Wellness Clinic", "healthcare", "Mumbai", "IN", False),
    ("Silverline Logistics Co.", "corporate", "Bengaluru", "IN", True),
    ("Cedar & Sage Cafe", "restaurant", "Austin", "US", False),
    ("Brightwater Pediatrics", "healthcare", "Pune", "IN", False),
    ("Atlas Coworking Spaces", "real_estate", "Hyderabad", "IN", True),
    ("Pebblestone Florists", "retail", "Mumbai", "IN", False),
    ("Vantage Accounting Group", "professional_services", "Bengaluru", "IN", True),
]

# Stage path each demo lead walks through (recorded as status.changed activities, like real usage).
PATH = ["discovered", "verified", "approved_for_outreach", "contacted", "interested", "qualified",
        "proposal_sent", "negotiation", "converted"]
# (final status, interest, budget min, budget max, timeline)
LEAD_PLAN = [
    ("converted", "high", 60000, 90000, "This month"),
    ("converted", "high", 40000, 60000, "Within 2 weeks"),
    ("converted", "medium", 25000, 35000, "Next month"),
    ("converted", "high", 120000, 150000, "This quarter"),
    ("negotiation", "high", 80000, 110000, "Within 30 days"),
    ("negotiation", "medium", 45000, 65000, "Next month"),
    ("proposal_sent", "high", 150000, 200000, "This quarter"),
    ("proposal_sent", "medium", 30000, 50000, None),
    ("qualified", "high", 70000, 90000, "Next month"),
    ("qualified", "medium", None, None, None),
    ("interested", "high", 20000, 30000, "ASAP"),
    ("interested", "low", None, None, None),
    ("contacted", "unknown", None, None, None),
    ("contacted", "medium", 15000, 25000, None),
    ("lost", "none", None, None, None),
    ("lost", "low", 10000, 15000, None),
    ("not_interested", "none", None, None, None),
    ("discovered", None, None, None, None),
]


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def find_demo(db: Session, user: User) -> DemoWorkspace | None:
    rows = db.scalars(select(DemoWorkspace).where(DemoWorkspace.owner_user_id == user.id)
                      .order_by(DemoWorkspace.created_at.desc())).all()
    for d in rows:
        org = db.get(Organization, d.organization_id)
        if org is not None and org.deleted_at is None:
            return d
    return None


def is_demo_org(db: Session, org_id: uuid.UUID) -> bool:
    return db.scalar(select(DemoWorkspace.id).where(DemoWorkspace.organization_id == org_id)) is not None


def create_demo(db: Session, user: User) -> DemoWorkspace:
    rnd = random.Random(42)  # deterministic sample data  # noqa: S311 (not security-relevant)
    now = utcnow()
    org = create_organization(db, user, DEMO_NAME, "IN")
    org.slug = f"demo-{secrets.token_hex(5)}"
    db.flush()
    set_tenant(db, org.id)
    oid = org.id
    counts: dict[str, int] = {}

    # ---- businesses + leads
    leads: list[Lead] = []
    for i, (name, industry, city, country, has_site) in enumerate(COMPANIES):
        age = timedelta(days=rnd.randint(1, 50), hours=rnd.randint(0, 23))
        domain = f"{_slug(name)}.example.com"
        b = Business(organization_id=oid, name=name, industry=industry, category=industry, city=city,
                     country=country, phone=f"+1-555-01{i:02d}", email=f"hello@{domain}",
                     website=f"https://{domain}" if has_site else None, website_domain=domain if has_site else None,
                     source="demo", is_simulated=True, verification_status="verified" if i % 3 else "unverified",
                     website_status="has_website" if has_site else "none", contact_permission_status="unknown",
                     collected_at=now - age, created_at=now - age, updated_at=now - age)
        db.add(b)
        db.flush()
        plan = LEAD_PLAN[i]
        lead = Lead(organization_id=oid, business_name=name, industry=industry, city=city, country=country,
                    phone=b.phone, email=b.email, website=b.website, source="demo", status=plan[0],
                    score=rnd.randint(35, 95), owner_user_id=user.id, created_at=now - age, updated_at=now - age,
                    consent_reference="DEMO-FICTIONAL-CONSENT" if plan[0] not in ("discovered",) else None,
                    custom_fields={"demo": True})
        crm.apply_contact_fields(lead)
        db.add(lead)
        db.flush()
        b.lead_id = lead.id
        leads.append(lead)
        db.add(LeadActivity(organization_id=oid, lead_id=lead.id, actor_user_id=user.id, type="lead.created",
                            data={"source": "demo", "status": "discovered"}, created_at=now - age))
        # Walk the lifecycle up to the final status so stage history is realistic.
        final = plan[0]
        steps = PATH[: PATH.index(final) + 1] if final in PATH else PATH[: rnd.randint(3, 6)] + [final]
        t = now - age
        for a, bb in zip(steps, steps[1:], strict=False):
            t = t + timedelta(hours=rnd.randint(6, 60))
            if t > now:
                t = now - timedelta(minutes=rnd.randint(5, 600))
            db.add(LeadActivity(organization_id=oid, lead_id=lead.id, actor_user_id=user.id, type="status.changed",
                                data={"from": a, "to": bb, "demo": True}, created_at=t))
        if plan[1]:
            o = ConversationOutcome(
                organization_id=oid, lead_id=lead.id, source="test_lab", extraction_mode="rules", model=None,
                interest=plan[1],
                budget_min=Decimal(plan[2]) if plan[2] else None, budget_max=Decimal(plan[3]) if plan[3] else None,
                budget_currency="INR" if plan[2] else None,
                budget_evidence="(fictional demo transcript) “We have set aside around this amount.”"
                if plan[2] else None,
                timeline=plan[4], next_step="Send proposal" if plan[1] == "high" else "Follow up next week",
                summary=f"Fictional demo conversation with {name}.", simulated=True, created_by=user.id,
                created_at=now - age / 2, updated_at=now - age / 2)
            db.add(o)
        if final in ("qualified", "negotiation", "interested", "proposal_sent"):
            due = now + timedelta(days=rnd.randint(-3, 5))
            db.add(LeadTask(organization_id=oid, lead_id=lead.id, title=f"Follow up with {name}", due_at=due,
                            assignee_user_id=user.id, created_by_user_id=user.id))
            db.add(LeadNote(organization_id=oid, lead_id=lead.id, author_user_id=user.id,
                            body="Demo note: fictional sample data for product walkthroughs."))
    counts["businesses"] = counts["leads"] = len(COMPANIES)

    # ---- AI agents + runs
    agents = []
    for name, status, industry in (("Aria — Dental Appointment Setter", "published", "healthcare"),
                                   ("Max — Real Estate Qualifier", "published", "real_estate"),
                                   ("Nova — Restaurant Reservations", "draft", "restaurant")):
        a = AIAgent(organization_id=oid, name=name, purpose="Fictional demo agent", industry=industry,
                    language="en", status=status, published_version=1 if status == "published" else None,
                    compliance_disclosure="This is an AI assistant calling on behalf of a demo company.",
                    greeting="Hi! This is a demo call.", created_by_user_id=user.id)
        db.add(a)
        agents.append(a)
    db.flush()
    for i in range(46):
        a = agents[i % 2]
        db.add(AgentRun(organization_id=oid, agent_id=a.id, kind="test", input={"demo": True},
                        output="(simulated demo run)", latency_ms=rnd.randint(380, 1400), provider="simulated",
                        model="template", simulated=True, actor_user_id=user.id,
                        created_at=now - timedelta(days=rnd.randint(0, 29), hours=rnd.randint(0, 23))))
    for o in db.scalars(select(ConversationOutcome).where(ConversationOutcome.organization_id == oid)):
        o.agent_id = agents[rnd.randint(0, 1)].id
    counts["agents"] = len(agents)

    # ---- websites (through the real generator + renderer)
    sites = 0
    for lead, tpl_key, publish in ((leads[1], "real_estate", True), (leads[3], "interior_design", True),
                                   (leads[0], "clinic", False), (leads[7], "professional_services", False)):
        tpl = _template(db, tpl_key)
        content = build_content({"name": lead.business_name, "industry": lead.industry, "city": lead.city,
                                 "country": lead.country, "phone": lead.phone, "email": lead.email},
                                {"key": tpl.key, "industry": tpl.industry, "sections": tpl.sections,
                                 "theme": tpl.theme})
        p = WebsiteProject(organization_id=oid, lead_id=lead.id, name=lead.business_name, template_key=tpl.key,
                           status="draft", preview_token=secrets.token_urlsafe(24), created_by=user.id)
        db.add(p)
        db.flush()
        v = _new_version(db, p, content, tpl.theme, user.id, "template", "Demo generation (fictional business)")
        if publish:
            p.approved_version_id = p.published_version_id = v.id
            p.status = "published"
        sites += 1
    counts["websites"] = sites

    # ---- campaigns
    for name, channel, status, spent in (("Pune clinics — website upgrade offer", "email", "running", "42.50"),
                                         ("Bengaluru realty follow-ups", "whatsapp", "running", "18.20"),
                                         ("Austin services — intro sequence", "email", "completed", "61.00"),
                                         ("Mumbai restaurants — Q4 launch", "email", "draft", "0")):
        db.add(Campaign(organization_id=oid, name=name, channel=channel, status=status, spent=Decimal(spent),
                        cost_per_message=Decimal("0.0100"), spend_limit=Decimal("100.00"),
                        created_by_user_id=user.id,
                        started_at=now - timedelta(days=6) if status != "draft" else None))
    counts["campaigns"] = 4

    # ---- marketplace referrals
    cat = ServiceCategory(organization_id=oid, slug="web-design", name="Web design", is_system=False)
    db.add(cat)
    db.flush()
    prov = ServiceProvider(organization_id=oid, business_name="Pixelcraft Studio (Demo)",
                           email="team@pixelcraft.example.org", description="Fictional demo provider",
                           service_areas=[{"city": "Pune", "country": "IN"}], experience_years=7,
                           verification_status="verified", currency="INR")
    db.add(prov)
    db.flush()
    for i, (cname, status, value) in enumerate((("Riya Demo", "converted", "85000"), ("Arjun Demo", "meeting", None),
                                                ("Sam Demo", "introduced", None))):
        cust = Customer(organization_id=oid, full_name=cname, email=f"customer{i}@example.com")
        db.add(cust)
        db.flush()
        req = CustomerRequirement(organization_id=oid, customer_id=cust.id, category_id=cat.id,
                                  title="New business website (fictional)", city="Pune", country="IN",
                                  budget_min=Decimal("50000"), budget_max=Decimal("100000"), currency="INR",
                                  contact_permission=True, consent_reference="DEMO-FICTIONAL", status="referred")
        db.add(req)
        db.flush()
        db.add(Referral(organization_id=oid, requirement_id=req.id, provider_id=prov.id, status=status,
                        deal_value=Decimal(value) if value else None, currency="INR", created_by=user.id))
    counts["referrals"] = 3

    # ---- workflow + executions
    graph = {"nodes": [{"id": "t", "type": "trigger.lead_created", "config": {}},
                       {"id": "a", "type": "action.create_task", "config": {"title": "Call new lead"}}],
             "edges": [{"source": "t", "target": "a"}]}
    wf = Workflow(organization_id=oid, name="New lead → follow-up task (demo)", status="active",
                  trigger_type="trigger.lead_created", draft_graph=graph, created_by_user_id=user.id)
    db.add(wf)
    db.flush()
    ver = WorkflowVersion(organization_id=oid, workflow_id=wf.id, version=1, graph=graph, created_by_user_id=user.id)
    db.add(ver)
    db.flush()
    wf.current_version_id = ver.id
    for i in range(12):
        t = now - timedelta(days=rnd.randint(0, 20))
        db.add(WorkflowExecution(organization_id=oid, workflow_id=wf.id, version_id=ver.id,
                                 status="failed" if i == 5 else "succeeded", trigger_type="trigger.lead_created",
                                 trigger_payload={"demo": True}, idempotency_key=f"demo-{i}", state={"outputs": {}},
                                 finished_at=t, created_at=t, updated_at=t, started_by_user_id=user.id))
    counts["workflow_runs"] = 12

    d = DemoWorkspace(organization_id=oid, owner_user_id=user.id, summary={"counts": counts, "fictional": True})
    db.add(d)
    db.flush()
    return d


SKIP_PURGE = {"organizations", "organization_memberships", "audit_logs", "demo_workspaces", "roles",
              "role_permissions", "sessions", "users"}


def delete_demo(db: Session, user: User, d: DemoWorkspace) -> None:
    """Soft-delete the demo organization (it disappears from every listing) and best-effort purge its rows."""
    org = db.get(Organization, d.organization_id)
    set_tenant(db, d.organization_id)
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in SKIP_PURGE or "organization_id" not in table.c:
            continue
        try:
            with db.begin_nested():
                db.execute(delete(table).where(table.c.organization_id == d.organization_id))
        except Exception as e:  # noqa: BLE001 - append-only tables may refuse deletes; org is soft-deleted anyway
            log.info("demo purge skipped %s: %s", table.name, type(e).__name__)
    if org is not None:
        org.deleted_at = utcnow()
        org.status = "suspended"
    m = db.scalar(select(OrganizationMembership).where(OrganizationMembership.organization_id == d.organization_id,
                                                       OrganizationMembership.user_id == user.id))
    if m is not None:
        m.status = "removed"
    summary = dict(d.summary or {})
    summary["deleted_at"] = utcnow().isoformat()
    d.summary = summary
