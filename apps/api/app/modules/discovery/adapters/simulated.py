"""Clearly-labelled simulated data. Used ONLY when the user explicitly selects source='simulated'.
Every record: source='simulated', is_simulated=True, name 'Simulated Business N', no real contact data."""
from app.modules.discovery.adapters.base import Adapter, RawBusiness, SearchResult

SOURCE = "simulated"


class SimulatedAdapter(Adapter):
    name = SOURCE
    label = "Simulated (demo data, not real businesses)"
    simulated = True

    def status(self) -> dict:
        return {"source": self.name, "label": self.label, "status": "available", "simulated": True,
                "detail": "Generates obviously fake records for demos and testing. Never real businesses."}

    def search(self, criteria: dict) -> SearchResult:
        n = max(1, min(int(criteria.get("limit") or 5), 20))
        records = []
        for i in range(1, n + 1):
            f = {"name": f"Simulated Business {i}", "industry": criteria.get("industry") or "simulated",
                 "category": criteria.get("category"), "city": criteria.get("city"),
                 "state": criteria.get("state"), "country": (criteria.get("country") or "")[:2].upper() or None,
                 "website": f"https://simulated-business-{i}.example" if i % 2 == 0 else None}
            records.append(RawBusiness(fields={k: v for k, v in f.items() if v}, source_ref=f"simulated-{i}"))
        return SearchResult(records=records, requests_made=0)
