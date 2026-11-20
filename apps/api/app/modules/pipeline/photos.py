"""Google Places photos: references + display-only proxy.

Maps Platform terms (summary of what this code enforces):
  * Photo references come only from the official Places API (`places.photos` in the field mask) and are stored as
    retention-limited provenance (field='photo'); the purge job nulls them on expiry.
  * Bytes are fetched on demand from `GET https://places.googleapis.com/v1/{photo_name}/media` for display INSIDE
    Leadex, streamed through, and never written to the database or disk (`Cache-Control: private, no-store`).
  * Author attributions are always returned with the photo and must be shown next to it.
  * Google photos are NOT copied into generated websites: the website generator accepts only BusinessImage rows
    (owner-supplied or the business's own website, with permission confirmed).
"""
import json
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import AppError
from app.modules.discovery import http
from app.modules.discovery.config import get_discovery_settings
from app.modules.discovery.models import BusinessSourceField
from app.modules.pipeline.config import pipeline_config

MEDIA_URL = "https://places.googleapis.com/v1/{name}/media"
ALLOWED_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif")
TOS_NOTE = ("Google Maps photo, shown inside Leadex for review only with its attribution. It is not stored and "
            "is never copied into generated websites (Google Maps Platform terms).")


def list_photo_refs(db: Session, org_id: uuid.UUID, business_id: uuid.UUID) -> list[dict]:
    now = utcnow()
    rows = db.scalars(select(BusinessSourceField).where(
        BusinessSourceField.organization_id == org_id, BusinessSourceField.business_id == business_id,
        BusinessSourceField.field == "photo", BusinessSourceField.purged_at.is_(None),
        BusinessSourceField.value.is_not(None))).all()
    out = []
    for r in rows:
        ret = r.retention_until
        if ret is not None and (ret.tzinfo is None and ret < now.replace(tzinfo=None) or
                                ret.tzinfo is not None and ret < now):
            continue  # expired, awaiting purge
        try:
            ph = json.loads(r.value)
        except ValueError:
            continue
        out.append({"name": ph.get("name"), "width": ph.get("widthPx"), "height": ph.get("heightPx"),
                    "attributions": [{"display_name": a.get("displayName"), "uri": a.get("uri")}
                                     for a in ph.get("authorAttributions") or []],
                    "source": "google_places", "retention_until": ret, "usable_in_website": False,
                    "notice": TOS_NOTE})
    return out


def fetch_photo(db: Session, org_id: uuid.UUID, business_id: uuid.UUID, name: str,
                max_width: int) -> tuple[bytes, str, list[dict]]:
    """Returns (bytes, content_type, attributions). Bytes are returned to the caller only — never persisted."""
    ref = next((p for p in list_photo_refs(db, org_id, business_id) if p["name"] == name), None)
    if ref is None:
        raise AppError(404, "not_found", "Photo not found for this business (or its retention expired)")
    key = get_discovery_settings().google_places_api_key
    if not key:
        raise AppError(409, "source_not_configured", "Set GOOGLE_PLACES_API_KEY to show Google photos")
    url = MEDIA_URL.format(name=name)
    try:
        with http.client(get_discovery_settings().http_timeout_s) as c:
            r = c.get(url, params={"maxWidthPx": max_width, "key": key})
    except httpx.HTTPError as e:
        raise AppError(502, "photo_fetch_failed", f"Google photo request failed: {type(e).__name__}") from e
    ctype = (r.headers.get("content-type") or "").split(";")[0].strip()
    if r.status_code != 200 or ctype not in ALLOWED_TYPES:
        raise AppError(502, "photo_fetch_failed", f"Google returned HTTP {r.status_code}")
    if len(r.content) > pipeline_config().google_photo_max_bytes:
        raise AppError(502, "photo_too_large", "Photo exceeds the proxy size limit")
    return r.content, ctype, ref["attributions"]
