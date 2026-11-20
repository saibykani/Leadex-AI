"""Permission catalog and system roles. Single source of truth used by migrations and tests."""

from sqlalchemy import select
from sqlalchemy.orm import Session

PERMISSIONS: dict[str, str] = {
    "org:read": "View organization",
    "org:write": "Edit organization settings",
    "members:read": "View members",
    "members:write": "Invite and manage members",
    "audit:read": "View audit logs",
    "businesses:read": "View businesses",
    "businesses:write": "Create and edit businesses",
    "discovery:run": "Run discovery searches",
    "leads:read": "View leads",
    "leads:write": "Create and edit leads",
    "agents:read": "View AI agents",
    "agents:write": "Configure AI agents",
    "calls:initiate": "Initiate voice calls",
    "campaigns:write": "Create campaigns",
    "campaigns:approve": "Approve campaigns",
    "websites:write": "Generate and edit websites",
    "websites:publish": "Publish websites",
    "marketplace:write": "Manage marketplace records",
    "commissions:manage": "Manage commissions",
    "workflows:write": "Build workflows",
    "billing:manage": "Manage billing",
    "integrations:manage": "Manage integrations",
}

_ALL = list(PERMISSIONS)
_READ = [p for p in _ALL if p.endswith(":read")]

SYSTEM_ROLES: dict[str, list[str]] = {
    "Owner": _ALL,
    "Admin": [p for p in _ALL if p != "billing:manage"],
    "Manager": _READ + ["leads:write", "businesses:write", "discovery:run", "campaigns:write",
                        "campaigns:approve", "websites:write", "agents:write", "workflows:write"],
    "Sales Rep": ["org:read", "members:read", "businesses:read", "leads:read", "leads:write", "agents:read"],
    "Viewer": [p for p in _READ if p != "audit:read"],
}


def seed_rbac(db: Session) -> None:
    """Idempotently create permissions and system roles (organization_id IS NULL)."""
    from app.modules.identity.models import Permission, Role

    existing = {p.code: p for p in db.scalars(select(Permission))}
    for code, desc in PERMISSIONS.items():
        if code not in existing:
            existing[code] = Permission(code=code, description=desc)
            db.add(existing[code])
    db.flush()
    for name, codes in SYSTEM_ROLES.items():
        role = db.scalar(select(Role).where(Role.organization_id.is_(None), Role.name == name))
        if role is None:
            role = Role(name=name, description=f"System role: {name}")
            db.add(role)
        role.permissions = [existing[c] for c in codes]
    db.commit()
