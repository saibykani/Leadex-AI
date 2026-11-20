"""Workflow graph validation and execution engine.

Execution model
---------------
A published version's graph is a DAG: {"nodes": [{"id", "type", "config"}], "edges": [{"source", "target", "label"?}]}.
Nodes are processed in a deterministic topological order. A node runs when at least one incoming edge is *active*:
the source node succeeded and, if the edge has a ``label``, it equals the source's output ``branch``
(condition -> "true"/"false", approval -> "approved"/"rejected", outreach -> "blocked"/"simulated"/"queued").
A node with no active incoming edge is ``skipped``. A filter that does not pass emits ``halt`` so nothing downstream
of it runs.

Progress is persisted in ``WorkflowExecution.state`` after every node, so execution is resumable and idempotent:
already-resolved nodes are never re-run. ``approval`` and ``delay`` nodes park the execution in ``waiting``.

Runners
-------
``SyncRunner`` executes inline inside the request (development / tests / single node). The engine only needs
``run_execution(db, execution_id)``, so a Celery or Temporal worker can replace the runner by implementing
``Runner.submit`` as e.g. ``run_workflow_task.delay(str(execution_id))`` whose task opens a session, binds the tenant
with ``set_tenant`` and calls ``run_execution``. Delays then become ``apply_async(eta=resume_at)`` (or a Temporal
timer) instead of the ``POST /workflows/executions/{id}/resume`` / ``resume-due`` polling endpoints.
"""
import hashlib
import ipaddress
import json
import os
import socket
import time
import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import AppError
from app.modules.automation.models import (
    AutomationSettings,
    WorkflowApproval,
    WorkflowExecution,
    WorkflowExecutionEvent,
    WorkflowVersion,
)

TRIGGER_TYPES = {"manual", "lead_created", "business_discovered", "webhook", "schedule"}
NODE_TYPES = {
    "trigger", "condition", "filter", "ai_action", "api_request", "email", "whatsapp", "voice_call", "crm_update",
    "lead_assignment", "delay", "approval", "webhook_out", "notification",
}
OUTREACH_CHANNEL = {"email": "email", "whatsapp": "whatsapp", "voice_call": "voice"}
MAX_NODES = 200
MAX_RETRIES = 5
MAX_TIMEOUT = 60.0


class NodeError(Exception):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class Pause(Exception):  # noqa: N818 (control-flow signal)
    def __init__(self, kind: str, output: dict, resume_at=None):
        super().__init__(kind)
        self.kind, self.output, self.resume_at = kind, output, resume_at


# ---------------------------------------------------------------- validation
def validate_graph(graph: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(graph, dict):
        return ["graph must be an object"]
    nodes, edges = graph.get("nodes") or [], graph.get("edges") or []
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return ["nodes and edges must be lists"]
    if not nodes:
        return ["graph has no nodes"]
    if len(nodes) > MAX_NODES:
        errors.append(f"too many nodes (max {MAX_NODES})")
    ids: set[str] = set()
    triggers = []
    for n in nodes:
        nid, typ = (n or {}).get("id"), (n or {}).get("type")
        if not isinstance(nid, str) or not nid:
            errors.append("every node needs a string id")
            continue
        if nid in ids:
            errors.append(f"duplicate node id '{nid}'")
        ids.add(nid)
        if typ not in NODE_TYPES:
            errors.append(f"node '{nid}': unknown type '{typ}'")
        cfg = n.get("config") or {}
        if not isinstance(cfg, dict):
            errors.append(f"node '{nid}': config must be an object")
            continue
        if typ == "trigger":
            triggers.append(nid)
            if cfg.get("trigger_type", "manual") not in TRIGGER_TYPES:
                errors.append(f"node '{nid}': trigger_type must be one of {sorted(TRIGGER_TYPES)}")
        if typ in {"condition", "filter"} and not cfg.get("field"):
            errors.append(f"node '{nid}': 'field' is required")
        if typ in {"api_request", "webhook_out"} and not cfg.get("url"):
            errors.append(f"node '{nid}': 'url' is required")
        if typ == "delay" and not isinstance(cfg.get("seconds", 0), int | float):
            errors.append(f"node '{nid}': 'seconds' must be a number")
        retries = cfg.get("retries", 0)
        if not isinstance(retries, int) or not 0 <= retries <= MAX_RETRIES:
            errors.append(f"node '{nid}': retries must be an integer 0..{MAX_RETRIES}")
        t = cfg.get("timeout_seconds", 10)
        if not isinstance(t, int | float) or not 0 < t <= MAX_TIMEOUT:
            errors.append(f"node '{nid}': timeout_seconds must be in (0, {MAX_TIMEOUT}]")
    if len(triggers) != 1:
        errors.append("graph must have exactly one trigger node")
    for e in edges:
        s, t = (e or {}).get("source"), (e or {}).get("target")
        if s not in ids or t not in ids:
            errors.append(f"edge {s}->{t} references an unknown node")
        elif s == t:
            errors.append(f"self-loop on '{s}'")
        elif triggers and t == triggers[0]:
            errors.append("the trigger node cannot have incoming edges")
    if not errors and topo_order(graph) is None:
        errors.append("graph contains a cycle")
    if not errors:
        reach = {triggers[0]}
        changed = True
        while changed:
            changed = False
            for e in edges:
                if e["source"] in reach and e["target"] not in reach:
                    reach.add(e["target"])
                    changed = True
        orphan = sorted(ids - reach)
        if orphan:
            errors.append(f"nodes not reachable from the trigger: {orphan}")
    return errors


def topo_order(graph: dict) -> list[str] | None:
    ids = [n["id"] for n in graph["nodes"]]
    indeg = {i: 0 for i in ids}
    out: dict[str, list[str]] = {i: [] for i in ids}
    for e in graph.get("edges") or []:
        out[e["source"]].append(e["target"])
        indeg[e["target"]] += 1
    ready = [i for i in ids if indeg[i] == 0]
    order: list[str] = []
    while ready:
        ready.sort(key=ids.index)
        n = ready.pop(0)
        order.append(n)
        for t in out[n]:
            indeg[t] -= 1
            if indeg[t] == 0:
                ready.append(t)
    return order if len(order) == len(ids) else None


def trigger_type_of(graph: dict) -> str:
    for n in graph["nodes"]:
        if n["type"] == "trigger":
            return (n.get("config") or {}).get("trigger_type", "manual")
    return "manual"


# ---------------------------------------------------------------- outbound HTTP (SSRF-guarded)
def _resolve(host: str) -> list[str]:
    return [ai[4][0] for ai in socket.getaddrinfo(host, None)]


def _http_client(timeout: float) -> httpx.Client:
    """Factory (tests swap in an httpx.MockTransport)."""
    return httpx.Client(timeout=timeout, follow_redirects=False)


def allowed_hosts(db: Session, org_id: uuid.UUID) -> list[str]:
    s = db.scalar(select(AutomationSettings).where(AutomationSettings.organization_id == org_id))
    return [h.lower() for h in (s.allowed_hosts or [])] if s else []


def guard_url(db: Session, org_id: uuid.UUID, url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise NodeError("only absolute http(s) URLs are allowed")
    host = parts.hostname.lower()
    if host not in allowed_hosts(db, org_id):
        raise NodeError(f"host '{host}' is not in this organization's allow-list")
    try:
        addrs = _resolve(host)
    except OSError as e:
        raise NodeError(f"cannot resolve host '{host}'", retryable=True) from e
    for a in addrs:
        ip = ipaddress.ip_address(a.split("%")[0])
        if not ip.is_global or ip.is_multicast:
            raise NodeError(f"host '{host}' resolves to a non-public address ({ip}); blocked (SSRF)")
    return url


def _http(db, org_id, cfg: dict, method: str, url: str, body) -> dict:
    guard_url(db, org_id, url)
    timeout = float(cfg.get("timeout_seconds", 10))
    try:
        with _http_client(timeout) as c:
            r = c.request(method, url, json=body, headers={"User-Agent": "LeadexAI-Workflows/1"})
    except httpx.TimeoutException as e:
        raise NodeError(f"timeout after {timeout}s", retryable=True) from e
    except httpx.HTTPError as e:
        raise NodeError(f"request failed: {e.__class__.__name__}", retryable=True) from e
    if r.status_code >= 500 or r.status_code == 429:
        raise NodeError(f"upstream returned {r.status_code}", retryable=True)
    if r.status_code >= 400:
        raise NodeError(f"upstream returned {r.status_code}")
    try:
        data = r.json()
    except ValueError:
        data = r.text[:2000]
    return {"status_code": r.status_code, "body": data}


# ---------------------------------------------------------------- context helpers
def _lookup(ctx: dict, path: str):
    cur = ctx
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _compare(left, op: str, right) -> bool:
    try:
        if op == "exists":
            return left is not None
        if op == "eq":
            return left == right
        if op == "ne":
            return left != right
        if op == "contains":
            return left is not None and str(right).lower() in str(left).lower()
        if op == "in":
            return left in (right or [])
        if left is None:
            return False
        lf, rf = float(left), float(right)
        return {"gt": lf > rf, "gte": lf >= rf, "lt": lf < rf, "lte": lf <= rf}[op]
    except (KeyError, TypeError, ValueError):
        return False


def _lead_dict(db, org_id, payload: dict) -> dict | None:
    from app.modules.crm.models import Lead

    lid = (payload or {}).get("lead_id")
    try:
        lead = db.get(Lead, uuid.UUID(str(lid))) if lid else None
    except ValueError:
        return None
    if lead is None or lead.organization_id != org_id or lead.deleted_at:
        return None
    return {"id": str(lead.id), "business_name": lead.business_name, "status": lead.status, "score": lead.score,
            "country": lead.country, "city": lead.city, "industry": lead.industry, "source": lead.source,
            "owner_user_id": str(lead.owner_user_id) if lead.owner_user_id else None}


def _lead_id(ex: WorkflowExecution, cfg: dict) -> uuid.UUID | None:
    raw = cfg.get("lead_id") or (ex.trigger_payload or {}).get("lead_id")
    try:
        return uuid.UUID(str(raw)) if raw else None
    except ValueError:
        return None


# ---------------------------------------------------------------- node handlers
def _h_trigger(db, ex, node, cfg, ctx):
    return {"trigger_type": ex.trigger_type, "payload": ex.trigger_payload or {}}


def _h_condition(db, ex, node, cfg, ctx):
    value = _lookup(ctx, cfg["field"])
    ok = _compare(value, cfg.get("op", "eq"), cfg.get("value"))
    return {"branch": "true" if ok else "false", "value": value}


def _h_filter(db, ex, node, cfg, ctx):
    value = _lookup(ctx, cfg["field"])
    ok = _compare(value, cfg.get("op", "eq"), cfg.get("value"))
    return {"passed": ok, "halt": not ok, "value": value}


def _h_ai_action(db, ex, node, cfg, ctx):
    prompt = str(cfg.get("prompt", "")).strip()[:4000]
    base = os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_URL")
    if not base:
        return {"simulated": True, "provider": "simulated",
                "text": f"[SIMULATED AI OUTPUT - no LLM configured] {prompt[:200]}"}
    timeout = float(cfg.get("timeout_seconds", 30))
    try:
        with _http_client(timeout) as c:  # Ollama is an operator-configured internal service, not tenant-controlled
            r = c.post(f"{base.rstrip('/')}/api/generate",
                       json={"model": cfg.get("model") or os.getenv("OLLAMA_MODEL", "llama3.1"),
                             "prompt": prompt, "stream": False})
    except httpx.TimeoutException as e:
        raise NodeError(f"LLM timeout after {timeout}s", retryable=True) from e
    except httpx.HTTPError as e:
        raise NodeError(f"LLM unavailable: {e.__class__.__name__}", retryable=True) from e
    if r.status_code != 200:
        raise NodeError(f"LLM returned {r.status_code}", retryable=r.status_code >= 500)
    return {"simulated": False, "provider": "ollama", "text": (r.json() or {}).get("response", "")[:8000]}


def _h_api_request(db, ex, node, cfg, ctx):
    return _http(db, ex.organization_id, cfg, str(cfg.get("method", "GET")).upper(), cfg["url"], cfg.get("body"))


def _h_webhook_out(db, ex, node, cfg, ctx):
    body = cfg.get("body") or {"workflow_id": str(ex.workflow_id), "execution_id": str(ex.id),
                               "payload": ex.trigger_payload or {}}
    return _http(db, ex.organization_id, cfg, "POST", cfg["url"], body)


def _h_outreach(db, ex, node, cfg, ctx):
    """email / whatsapp / voice_call: NEVER send. Record the OutreachGate decision only; delivery is delegated to the
    communication / voice modules which re-check the gate themselves."""
    from app.modules.compliance.gate import check_outreach

    channel = OUTREACH_CHANNEL[node["type"]]
    lead_id = _lead_id(ex, cfg)
    if lead_id is None:
        return {"branch": "blocked", "channel": channel, "delivery": "blocked", "reasons": ["lead_id_missing"]}
    d = check_outreach(db, ex.organization_id, lead_id, channel)
    if not d.allowed:
        delivery = "blocked"
    elif d.simulated:
        delivery = "simulated"
    else:
        delivery = "queued"  # handed to the channel module; this engine has no sending adapter
    return {"branch": delivery, "channel": channel, "lead_id": str(lead_id), "delivery": delivery,
            "gate": {"allowed": d.allowed, "simulated": d.simulated, "reasons": d.reasons},
            "simulated": d.simulated, "template": cfg.get("template")}


def _h_crm_update(db, ex, node, cfg, ctx):
    from app.modules.crm import service as crm
    from app.modules.crm.models import Lead, LeadActivity

    lead_id = _lead_id(ex, cfg)
    lead = db.get(Lead, lead_id) if lead_id else None
    if lead is None or lead.organization_id != ex.organization_id or lead.deleted_at:
        raise NodeError("lead not found")
    changed: dict = {}
    if cfg.get("status"):
        if cfg["status"] in crm.CONSENT_REQUIRED:
            raise NodeError("workflows may not grant outreach approval; consent requires a human")
        if cfg["status"] not in crm.TRANSITIONS.get(lead.status, frozenset()):
            raise NodeError(f"invalid transition {lead.status} -> {cfg['status']}")
        changed["status"] = {"from": lead.status, "to": cfg["status"]}
        lead.status = cfg["status"]
    if "score" in cfg and cfg["score"] is not None:
        changed["score"] = lead.score = int(cfg["score"])
    if isinstance(cfg.get("custom_fields"), dict):
        lead.custom_fields = {**(lead.custom_fields or {}), **cfg["custom_fields"]}
        changed["custom_fields"] = sorted(cfg["custom_fields"])
    db.add(LeadActivity(organization_id=ex.organization_id, lead_id=lead.id, actor_user_id=None,
                        type="workflow.crm_update", data={"execution_id": str(ex.id), **changed}))
    return {"lead_id": str(lead.id), "changed": changed}


def _h_lead_assignment(db, ex, node, cfg, ctx):
    from app.modules.crm.models import Lead
    from app.modules.identity.models import OrganizationMembership

    lead_id = _lead_id(ex, cfg)
    lead = db.get(Lead, lead_id) if lead_id else None
    if lead is None or lead.organization_id != ex.organization_id or lead.deleted_at:
        raise NodeError("lead not found")
    members = db.scalars(select(OrganizationMembership.user_id).where(
        OrganizationMembership.organization_id == ex.organization_id,
        OrganizationMembership.status == "active")).all()
    if cfg.get("user_id"):
        try:
            uid = uuid.UUID(str(cfg["user_id"]))
        except ValueError as e:
            raise NodeError("invalid user_id") from e
        if uid not in members:
            raise NodeError("assignee is not an active member of this organization")
    else:  # least-loaded active member
        if not members:
            raise NodeError("no active members")
        counts = dict(db.execute(select(Lead.owner_user_id, func.count()).where(
            Lead.organization_id == ex.organization_id, Lead.deleted_at.is_(None)).group_by(Lead.owner_user_id)).all())
        uid = min(sorted(members, key=str), key=lambda m: counts.get(m, 0))
    lead.owner_user_id = uid
    return {"lead_id": str(lead.id), "owner_user_id": str(uid)}


def _h_delay(db, ex, node, cfg, ctx):
    resume_at = utcnow() + timedelta(seconds=float(cfg.get("seconds", 0)))
    raise Pause("waiting_delay", {"resume_at": resume_at.isoformat()}, resume_at)


def _h_approval(db, ex, node, cfg, ctx):
    db.add(WorkflowApproval(organization_id=ex.organization_id, execution_id=ex.id, node_key=node["id"],
                            message=cfg.get("message")))
    raise Pause("waiting_approval", {"message": cfg.get("message")})


def _h_notification(db, ex, node, cfg, ctx):
    return {"notified": cfg.get("recipients") or "workspace", "message": str(cfg.get("message", ""))[:1000],
            "channel": "in_app"}


HANDLERS: dict[str, Callable] = {
    "trigger": _h_trigger, "condition": _h_condition, "filter": _h_filter, "ai_action": _h_ai_action,
    "api_request": _h_api_request, "webhook_out": _h_webhook_out, "email": _h_outreach, "whatsapp": _h_outreach,
    "voice_call": _h_outreach, "crm_update": _h_crm_update, "lead_assignment": _h_lead_assignment,
    "delay": _h_delay, "approval": _h_approval, "notification": _h_notification,
}


# ---------------------------------------------------------------- runtime
def _event(db, ex, node, event, attempt=1, output=None, error=None):
    state = ex.state or {}
    seq = state.get("seq", 0) + 1
    ex.state = {**state, "seq": seq}
    db.add(WorkflowExecutionEvent(organization_id=ex.organization_id, execution_id=ex.id, seq=seq,
                                  node_key=node["id"] if node else None, node_type=node["type"] if node else None,
                                  event=event, attempt=attempt, output=output, error=error))


def _edge_active(edge: dict, resolved: dict, outputs: dict) -> bool:
    if resolved.get(edge["source"]) != "succeeded":
        return False
    out = outputs.get(edge["source"]) or {}
    if out.get("halt"):
        return False
    label = edge.get("label")
    if not label:  # unlabelled edges follow every outcome except an explicit "halt_unlabelled" (e.g. rejection)
        return not out.get("halt_unlabelled")
    return label == out.get("branch")


def _finish(ex, status, error=None):
    ex.status, ex.error, ex.finished_at, ex.resume_at = status, error, utcnow(), None
    ex.state = {**(ex.state or {}), "waiting_on": None}


def run_execution(db: Session, execution_id: uuid.UUID, *, resume_output: dict | None = None) -> WorkflowExecution:
    """Advance an execution as far as possible. Safe to call repeatedly (resolved nodes are never re-run)."""
    ex = db.get(WorkflowExecution, execution_id)
    if ex is None or ex.status in {"succeeded", "failed", "cancelled"}:
        return ex
    graph = db.get(WorkflowVersion, ex.version_id).graph
    nodes = {n["id"]: n for n in graph["nodes"]}
    order = topo_order(graph) or []
    state = dict(ex.state or {})
    outputs, resolved = dict(state.get("outputs") or {}), dict(state.get("resolved") or {})
    waiting = state.get("waiting_on")
    if waiting:  # completing a paused node
        if resume_output is None:
            return ex
        outputs[waiting], resolved[waiting] = resume_output, "succeeded"
        ex.state = {**state, "outputs": outputs, "resolved": resolved, "waiting_on": None}
        _event(db, ex, nodes[waiting], "succeeded", output=resume_output)
    ex.status, ex.resume_at = "running", None
    lead = _lead_dict(db, ex.organization_id, ex.trigger_payload or {})
    for nid in order:
        if nid in resolved:
            continue
        node = nodes[nid]
        incoming = [e for e in graph.get("edges") or [] if e["target"] == nid]
        if node["type"] != "trigger" and not any(_edge_active(e, resolved, outputs) for e in incoming):
            resolved[nid] = "skipped"
            ex.state = {**ex.state, "resolved": resolved}
            _event(db, ex, node, "skipped")
            continue
        cfg = node.get("config") or {}
        retries = int(cfg.get("retries", 0))
        timeout = float(cfg.get("timeout_seconds", 10))
        ctx = {"payload": ex.trigger_payload or {}, "nodes": outputs, "lead": lead}
        attempt = 0
        while True:
            attempt += 1
            _event(db, ex, node, "started", attempt)
            t0 = time.monotonic()
            try:
                out = HANDLERS[node["type"]](db, ex, node, cfg, ctx)
                if time.monotonic() - t0 > timeout:
                    raise NodeError(f"timeout after {timeout}s", retryable=True)
            except Pause as p:
                outputs[nid] = p.output
                ex.state = {**ex.state, "outputs": outputs, "resolved": resolved, "waiting_on": nid}
                ex.status, ex.resume_at = "waiting", p.resume_at
                _event(db, ex, node, p.kind, attempt, output=p.output)
                db.flush()
                return ex
            except NodeError as e:
                if e.retryable and attempt <= retries:
                    _event(db, ex, node, "retried", attempt, error=str(e))
                    continue
                _event(db, ex, node, "failed", attempt, error=str(e))
                if cfg.get("continue_on_error"):
                    outputs[nid], resolved[nid] = {"error": str(e), "branch": "error"}, "succeeded"
                    break
                resolved[nid] = "failed"
                ex.state = {**ex.state, "outputs": outputs, "resolved": resolved}
                _finish(ex, "failed", f"node '{nid}': {e}")
                db.flush()
                return ex
            outputs[nid], resolved[nid] = _jsonable(out), "succeeded"
            _event(db, ex, node, "succeeded", attempt, output=outputs[nid])
            break
        ex.state = {**ex.state, "outputs": outputs, "resolved": resolved}
    _finish(ex, "succeeded")
    db.flush()
    return ex


def _jsonable(v):
    return json.loads(json.dumps(v, default=str))


class Runner(Protocol):
    def submit(self, db: Session, execution_id: uuid.UUID) -> None: ...


class SyncRunner:
    """In-process runner. Replace with a Celery/Temporal-backed Runner for production scale (see module docstring)."""

    def submit(self, db: Session, execution_id: uuid.UUID) -> None:
        run_execution(db, execution_id)


runner: Runner = SyncRunner()


def start_execution(db: Session, *, workflow, trigger_type: str, payload: dict | None, idempotency_key: str | None,
                    user_id: uuid.UUID | None) -> tuple[WorkflowExecution, bool]:
    """Create (or return the existing, for a repeated Idempotency-Key) execution; submit it. Returns (ex, created)."""
    if workflow.current_version_id is None:
        raise AppError(409, "not_published", "Publish a version before running this workflow")
    if workflow.status != "active":
        raise AppError(409, "workflow_inactive", f"Workflow is {workflow.status}")
    key = (idempotency_key or "").strip()[:200] or f"auto:{uuid.uuid4()}"
    existing = db.scalar(select(WorkflowExecution).where(WorkflowExecution.workflow_id == workflow.id,
                                                         WorkflowExecution.idempotency_key == key))
    if existing is not None:
        return existing, False
    ex = WorkflowExecution(organization_id=workflow.organization_id, workflow_id=workflow.id,
                           version_id=workflow.current_version_id, trigger_type=trigger_type,
                           trigger_payload=payload or {}, idempotency_key=key, state={},
                           started_by_user_id=user_id, status="queued")
    db.add(ex)
    db.flush()
    runner.submit(db, ex.id)
    return ex, True


def dispatch_event(db: Session, organization_id: uuid.UUID, trigger_type: str, payload: dict,
                   event_id: str | None = None) -> list[WorkflowExecution]:
    """Hook for other modules (crm on lead creation -> 'lead_created', discovery -> 'business_discovered',
    a scheduler -> 'schedule'). Starts every active workflow of the tenant whose trigger matches. Caller commits."""
    from app.modules.automation.models import Workflow

    wfs = db.scalars(select(Workflow).where(Workflow.organization_id == organization_id,
                                            Workflow.status == "active", Workflow.trigger_type == trigger_type,
                                            Workflow.deleted_at.is_(None))).all()
    key = f"event:{trigger_type}:{event_id}" if event_id else None
    return [start_execution(db, workflow=w, trigger_type=trigger_type, payload=payload, idempotency_key=key,
                            user_id=None)[0] for w in wfs]


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()
