from app.modules.discovery.adapters.base import Adapter, AdapterError, RawBusiness, SearchResult
from app.modules.discovery.adapters.csv_import import CsvImportAdapter
from app.modules.discovery.adapters.google_places import GooglePlacesAdapter
from app.modules.discovery.adapters.simulated import SimulatedAdapter

ADAPTERS: dict[str, Adapter] = {a.name: a for a in (GooglePlacesAdapter(), CsvImportAdapter(), SimulatedAdapter())}

__all__ = ["ADAPTERS", "Adapter", "AdapterError", "RawBusiness", "SearchResult", "CsvImportAdapter",
           "GooglePlacesAdapter", "SimulatedAdapter"]
