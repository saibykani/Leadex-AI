from dataclasses import dataclass, field
from datetime import datetime


class AdapterError(Exception):
    """Provider call failed. Message is safe to show to the user (no secrets)."""


@dataclass
class RawBusiness:
    fields: dict  # business column -> value
    source_ref: str | None = None
    place_id: str | None = None
    # field -> retention deadline (None = no provider-imposed limit)
    retention: dict[str, datetime] = field(default_factory=dict)
    website_known_absent: bool = False  # provider explicitly returned no website for a requested website field


@dataclass
class SearchResult:
    records: list[RawBusiness]
    requests_made: int = 0  # billable provider requests
    usage_resource: str | None = None
    unit_cost: float | None = None


class Adapter:
    name: str = ""
    label: str = ""
    simulated: bool = False
    supports_search: bool = True

    def status(self) -> dict:
        raise NotImplementedError

    def search(self, criteria: dict) -> SearchResult:
        raise NotImplementedError
