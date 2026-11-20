import csv
import io
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.errors import AppError
from app.core.tenancy import TenantContext, audit, require_permission
from app.modules.dnc import service as svc
from app.modules.dnc.models import DncEntry, DncImport

router = APIRouter(prefix="/compliance/dnc", tags=["dnc"])
READ = require_permission("leads:read")
ADMIN = require_permission("org:write")
MAX_BYTES = 50 * 1024 * 1024


@router.get("/status")
def status(ctx: TenantContext = Depends(READ), db: Session = Depends(get_db)):
    out = []
    for cc, name in svc.REGISTRY_COUNTRIES.items():
        imp = svc.latest_import(db, ctx.organization_id, cc)
        n = db.scalar(select(func.count()).select_from(DncEntry).where(DncEntry.organization_id == ctx.organization_id,
                                                                       DncEntry.country == cc)) or 0
        created = imp.created_at if imp and imp.created_at.tzinfo else (
            imp.created_at.replace(tzinfo=utcnow().tzinfo) if imp else None)
        out.append({"country": cc, "registry": name, "entries": n, "last_import_at": created,
                    "fresh": bool(created and utcnow() - created <= timedelta(days=svc.max_age_days()))})
    return {"enforced": svc.enforced(), "max_age_days": svc.max_age_days(),
            "api_configured": bool(__import__("os").getenv("DNC_API_URL")), "countries": out}


@router.post("/import", status_code=201)
async def import_registry(request: Request, country: str = Form(..., min_length=2, max_length=2),
                          replace: bool = Form(True), file: UploadFile = File(...),
                          ctx: TenantContext = Depends(ADMIN), db: Session = Depends(get_db)):
    """CSV/TXT of registry numbers: one number per line, or a column named phone/number/msisdn."""
    cc = country.upper()
    if cc not in svc.REGISTRY_COUNTRIES:
        raise AppError(422, "unsupported_country", f"Registry import supported for {sorted(svc.REGISTRY_COUNTRIES)}")
    raw = await file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise AppError(413, "file_too_large", "Registry file is larger than 50 MB; split it")
    from app.core.scanning import scan_bytes

    scan_bytes(raw, file.filename or "dnc.csv")
    text = raw.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    col = 0
    if rows and any(h.strip().lower() in {"phone", "number", "msisdn", "mobile"} for h in rows[0]):
        col = next(i for i, h in enumerate(rows[0]) if h.strip().lower() in {"phone", "number", "msisdn", "mobile"})
        rows = rows[1:]
    numbers, rejected = set(), 0
    for r in rows:
        v = r[col].strip() if len(r) > col else ""
        n = svc.e164(v, cc) if v else None
        if n:
            numbers.add(n)
        elif v:
            rejected += 1
    if replace:
        db.execute(delete(DncEntry).where(DncEntry.organization_id == ctx.organization_id, DncEntry.country == cc))
    imp = DncImport(organization_id=ctx.organization_id, country=cc, source=(file.filename or "upload")[:200],
                    rows=len(numbers), rejected=rejected, imported_by_user_id=ctx.user.id)
    db.add(imp)
    db.flush()
    db.add_all([DncEntry(id=uuid.uuid4(), organization_id=ctx.organization_id, country=cc, phone_e164=n,
                         import_id=imp.id) for n in numbers])
    audit(db, "dnc.import", org_id=ctx.organization_id, user_id=ctx.user.id, entity_type="dnc_import",
          entity_id=imp.id, data={"country": cc, "rows": len(numbers), "rejected": rejected}, request=request)
    db.commit()
    return {"id": imp.id, "country": cc, "imported": len(numbers), "rejected": rejected}
