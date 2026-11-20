"""Business-owned images: validation, storage and import from the business's OWN website.

Rules:
  * Only PNG / JPEG / WEBP, <= image_max_bytes (5 MB), verified by magic bytes (not the filename or the
    client-supplied content type).
  * Uploads (`owner_supplied`) require the uploader to confirm they have permission to use the images.
  * Website imports (`from_business_website`) start as `pending_review`; they are usable in generated websites
    only after a user confirms permission (approve).
  * Google Places photos never enter this table (see photos.py): they may not be copied into websites.
"""
import hashlib
import re
import secrets
import uuid
from urllib.parse import urljoin, urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import AppError
from app.core.tenancy import TenantContext
from app.modules.discovery import http
from app.modules.discovery import website_audit as wa
from app.modules.discovery.models import Business
from app.modules.pipeline.config import pipeline_config
from app.modules.pipeline.models import BusinessImage

SOURCES = ("owner_supplied", "from_business_website")
USABLE_SOURCES = SOURCES  # Google photos are not a usable source, by construction
MAX_REDIRECTS = 3
HOMEPAGE_MAX_BYTES = 2_000_000


def sniff(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate(data: bytes) -> str:
    if not data:
        raise AppError(422, "empty_image", "The image is empty")
    if len(data) > pipeline_config().image_max_bytes:
        raise AppError(413, "image_too_large", "Images must be 5 MB or smaller")
    ctype = sniff(data)
    if ctype is None:
        raise AppError(415, "unsupported_image", "Only PNG, JPEG or WEBP images are accepted (checked by content)")
    return ctype


def create_image(db: Session, ctx: TenantContext, biz: Business, data: bytes, *, source: str,
                 permission_confirmed: bool, filename: str | None = None, origin_url: str | None = None,
                 alt: str | None = None) -> BusinessImage:
    ctype = validate(data)
    approved = source == "owner_supplied" and permission_confirmed
    now = utcnow()
    img = BusinessImage(
        organization_id=ctx.organization_id, business_id=biz.id, source=source,
        status="approved" if approved else "pending_review", permission_confirmed=approved,
        permission_confirmed_by=ctx.user.id if approved else None, permission_confirmed_at=now if approved else None,
        content_type=ctype, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), data=data,
        origin_url=origin_url, filename=(filename or "")[:255] or None, alt=(alt or biz.name or "")[:300] or None,
        public_token=secrets.token_urlsafe(32), uploaded_by=ctx.user.id)
    db.add(img)
    db.flush()
    return img


def get_image(db: Session, ctx: TenantContext, biz_id: uuid.UUID, image_id: uuid.UUID) -> BusinessImage:
    img = db.scalar(select(BusinessImage).where(BusinessImage.id == image_id, BusinessImage.business_id == biz_id,
                                                BusinessImage.organization_id == ctx.organization_id))
    if img is None:
        raise AppError(404, "not_found", "Image not found")
    return img


def public_url(img: BusinessImage) -> str:
    return f"{pipeline_config().public_api_url.rstrip('/')}/api/v1/public/media/{img.public_token}"


def resolve_for_website(db: Session, ctx: TenantContext, image_ids: list[uuid.UUID],
                        business_id: uuid.UUID | None = None) -> list[dict]:
    """Website generator hook. Every id must be an approved, permission-confirmed image of this tenant.
    Google Places photos cannot be passed: they are not BusinessImage rows (Maps Platform terms)."""
    out = []
    for iid in image_ids:
        img = db.scalar(select(BusinessImage).where(BusinessImage.id == iid,
                                                    BusinessImage.organization_id == ctx.organization_id))
        if img is None or (business_id and img.business_id != business_id):
            raise AppError(404, "image_not_found", f"Image {iid} not found for this business")
        if img.status != "approved" or not img.permission_confirmed or img.source not in USABLE_SOURCES:
            raise AppError(422, "image_not_approved",
                           "Only images with confirmed permission can be used in a website",
                           {"image_id": str(iid), "status": img.status})
        out.append({"id": str(img.id), "url": public_url(img), "alt": img.alt or "", "source": img.source})
    return out


# ------------------------------------------------------------------ import from the business's own website
_OG = re.compile(r"""<meta[^>]+(?:property|name)=["']og:image(?::url)?["'][^>]*>""", re.I)
_CONTENT = re.compile(r"""content=["']([^"']+)["']""", re.I)
_IMG = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.I)


def _get(c: httpx.Client, url: str, max_bytes: int) -> tuple[httpx.Response, bytes]:
    """SSRF-safe GET: every hop (including redirects) is checked by the discovery guard; body size capped."""
    for _ in range(MAX_REDIRECTS + 1):
        wa.guard_target(url)
        with c.stream("GET", url) as r:
            if r.is_redirect and r.headers.get("location"):
                url = urljoin(url, r.headers["location"])
                continue
            buf = b""
            for chunk in r.iter_bytes():
                buf += chunk
                if len(buf) > max_bytes:
                    raise ValueError("too_large")
            return r, buf
    raise ValueError("too_many_redirects")


def candidate_urls(html: str, base: str) -> list[str]:
    found = []
    for tag in _OG.findall(html):
        m = _CONTENT.search(tag)
        if m:
            found.append(m.group(1))
    found += _IMG.findall(html)
    out, seen = [], set()
    for u in found:
        u = u.strip()
        if not u or u.startswith("data:") or u.lower().split("?")[0].endswith(".svg"):
            continue
        full = urljoin(base, u)
        if urlsplit(full).scheme in ("http", "https") and full not in seen:
            seen.add(full)
            out.append(full)
    return out


def import_from_website(db: Session, ctx: TenantContext, biz: Business) -> dict:
    if not biz.website:
        raise AppError(422, "no_website", "This business has no website on record")
    if biz.is_simulated:
        raise AppError(422, "simulated_business", "Simulated businesses have no real website")
    cfg = pipeline_config()
    url = wa.normalize_url(biz.website)
    imported, skipped = [], []
    try:
        with http.client(10, follow_redirects=False) as c:
            r, body = _get(c, url, HOMEPAGE_MAX_BYTES)
            if r.status_code != 200:
                raise AppError(502, "website_fetch_failed", f"The website returned HTTP {r.status_code}")
            urls = candidate_urls(body.decode("utf-8", "replace"), str(r.url))[: cfg.website_import_max_images]
            existing = set(db.scalars(select(BusinessImage.origin_url).where(
                BusinessImage.business_id == biz.id, BusinessImage.organization_id == ctx.organization_id)))
            for u in urls:
                if u in existing:
                    skipped.append({"url": u, "reason": "already_imported"})
                    continue
                try:
                    ir, data = _get(c, u, cfg.image_max_bytes)
                    if ir.status_code != 200:
                        skipped.append({"url": u, "reason": f"http_{ir.status_code}"})
                        continue
                    if sniff(data) is None:
                        skipped.append({"url": u, "reason": "not_png_jpeg_webp"})
                        continue
                    imported.append(create_image(db, ctx, biz, data, source="from_business_website",
                                                 permission_confirmed=False, origin_url=u[:1000]))
                except ValueError as e:
                    skipped.append({"url": u, "reason": str(e)})
                except wa.BlockedTarget:
                    skipped.append({"url": u, "reason": "blocked_non_public_address"})
                except httpx.HTTPError as e:
                    skipped.append({"url": u, "reason": type(e).__name__})
    except wa.BlockedTarget as e:
        raise AppError(422, "blocked_target", str(e)) from e
    except ValueError as e:
        raise AppError(502, "website_fetch_failed", f"Homepage could not be read: {e}") from e
    except httpx.HTTPError as e:
        raise AppError(502, "website_fetch_failed", f"Website unreachable: {type(e).__name__}") from e
    return {"imported": imported, "skipped": skipped}
