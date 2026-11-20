"""Google Places API (New) Text Search adapter.

Terms of service notes (Google Maps Platform):
  * Only official API access; no scraping of Google Maps.
  * Place content may be cached only temporarily, so every Google-derived field gets `retention_until`
    (GOOGLE_PLACES_RETENTION_DAYS, default 30) and is purged by `service.purge_expired_provider_fields`.
    `place_id` is exempt and kept long-term so the place can be refreshed.
  * The field mask is kept minimal; phone/website fields bill at a higher SKU (see INTEGRATION_MATRIX).
"""
from datetime import timedelta

import httpx

from app.core.db import utcnow
from app.modules.discovery import http
from app.modules.discovery.adapters.base import Adapter, AdapterError, RawBusiness, SearchResult
from app.modules.discovery.config import get_discovery_settings

URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join([
    "places.id", "places.displayName", "places.formattedAddress", "places.addressComponents",
    "places.location", "places.primaryType", "places.nationalPhoneNumber", "places.websiteUri",
    # Photo *references* only (name, size, authorAttributions). Bytes are fetched on demand through the
    # pipeline photo proxy for display inside Leadex, with attribution, and are never stored or copied into
    # generated websites (Maps Platform terms). References are retention-limited like other Places content.
    "places.photos",
])
MAX_PHOTOS = 10
SOURCE = "google_places"


def build_query(c: dict) -> str:
    what = " ".join(x for x in (c.get("name"), c.get("category") or c.get("industry")) if x) or "businesses"
    where = ", ".join(x for x in (c.get("locality"), c.get("city"), c.get("state"), c.get("postal_code"),
                                  c.get("country")) if x)
    return f"{what} in {where}" if where else what


def _component(comps: list, kind: str, short: bool = False) -> str | None:
    for comp in comps or []:
        if kind in comp.get("types", []):
            return comp.get("shortText" if short else "longText")
    return None


class GooglePlacesAdapter(Adapter):
    name = SOURCE
    label = "Google Places (official API)"

    def status(self) -> dict:
        ok = get_discovery_settings().google_places_api_key is not None
        return {"source": self.name, "label": self.label, "status": "configured" if ok else "not_configured",
                "simulated": False,
                "detail": None if ok else "Set GOOGLE_PLACES_API_KEY to enable Google Places discovery."}

    def search(self, criteria: dict) -> SearchResult:
        s = get_discovery_settings()
        if not s.google_places_api_key:
            raise AdapterError("Google Places is not configured (GOOGLE_PLACES_API_KEY missing)")
        body: dict = {"textQuery": build_query(criteria), "pageSize": min(int(criteria.get("limit") or 20), 20)}
        if criteria.get("country"):
            body["regionCode"] = criteria["country"].lower()
        headers = {"X-Goog-Api-Key": s.google_places_api_key, "X-Goog-FieldMask": FIELD_MASK}
        try:
            with http.client(s.http_timeout_s) as c:
                r = c.post(URL, json=body, headers=headers)
        except httpx.HTTPError as e:
            raise AdapterError(f"Google Places request failed: {type(e).__name__}") from e
        result = SearchResult(records=[], requests_made=1, usage_resource="google_places_request",
                              unit_cost=s.google_unit_cost)
        if r.status_code != 200:
            try:
                msg = r.json().get("error", {}).get("message", "")
            except ValueError:
                msg = ""
            err = AdapterError(f"Google Places returned HTTP {r.status_code}{': ' + msg[:200] if msg else ''}")
            err.result = result  # the request was still made (and may be billed)
            raise err
        until = utcnow() + timedelta(days=s.google_retention_days)
        for p in r.json().get("places", []) or []:
            pid = p.get("id")
            if not pid:
                continue
            comps = p.get("addressComponents") or []
            loc = p.get("location") or {}
            f = {
                "name": (p.get("displayName") or {}).get("text"),
                "address": p.get("formattedAddress"),
                "category": p.get("primaryType"),
                "phone": p.get("nationalPhoneNumber"),
                "website": p.get("websiteUri"),
                "lat": loc.get("latitude"),
                "lng": loc.get("longitude"),
                "country": _component(comps, "country", short=True),
                "state": _component(comps, "administrative_area_level_1"),
                "city": _component(comps, "locality"),
                "locality": _component(comps, "sublocality") or _component(comps, "neighborhood"),
                "postal_code": _component(comps, "postal_code"),
            }
            if criteria.get("industry"):
                f["industry"] = criteria["industry"]  # user-supplied label, not Google content
            photos = [{"name": ph.get("name"), "widthPx": ph.get("widthPx"), "heightPx": ph.get("heightPx"),
                       "authorAttributions": ph.get("authorAttributions") or []}
                      for ph in (p.get("photos") or [])[:MAX_PHOTOS] if ph.get("name")]
            if photos:
                f["photos"] = photos
            f = {k: v for k, v in f.items() if v not in (None, "")}
            retention = {k: until for k in f if k != "industry"}
            result.records.append(RawBusiness(fields=f, source_ref=pid, place_id=pid, retention=retention,
                                              website_known_absent="website" not in f))
        return result
