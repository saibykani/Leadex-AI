"""Discovery settings, read from the environment on every call (cheap; lets tests override via monkeypatch)."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoverySettings:
    google_places_api_key: str | None
    daily_request_budget: int  # external (billable) provider requests per organization per UTC day
    google_retention_days: int
    google_unit_cost: float  # informational; reconcile with your Google Cloud SKU pricing
    http_timeout_s: float
    audit_max_retries: int


def get_discovery_settings() -> DiscoverySettings:
    env = os.environ.get
    return DiscoverySettings(
        google_places_api_key=(env("GOOGLE_PLACES_API_KEY") or "").strip() or None,
        daily_request_budget=int(env("DISCOVERY_DAILY_REQUEST_BUDGET", "100")),
        google_retention_days=int(env("GOOGLE_PLACES_RETENTION_DAYS", "30")),
        google_unit_cost=float(env("GOOGLE_PLACES_UNIT_COST", "0.035")),
        http_timeout_s=float(env("DISCOVERY_HTTP_TIMEOUT", "10")),
        audit_max_retries=min(2, int(env("WEBSITE_AUDIT_MAX_RETRIES", "2"))),
    )
