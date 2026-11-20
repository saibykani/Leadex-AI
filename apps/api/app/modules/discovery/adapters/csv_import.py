"""Customer-supplied CSV import. The customer warrants they may use the data they upload."""
import csv
import io

from app.modules.discovery.adapters.base import Adapter, AdapterError, RawBusiness, SearchResult

SOURCE = "customer_import"
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000
COLUMNS = ("name", "industry", "category", "address", "country", "state", "city", "locality", "postal_code",
           "phone", "email", "website")
ALIASES = {"business_name": "name", "company": "name", "zip": "postal_code", "pincode": "postal_code",
           "url": "website", "telephone": "phone"}


COUNTRY_NAMES = {"india": "IN", "united arab emirates": "AE", "uae": "AE", "united kingdom": "GB", "uk": "GB",
                 "great britain": "GB", "england": "GB", "united states": "US", "usa": "US",
                 "united states of america": "US", "singapore": "SG", "australia": "AU", "canada": "CA"}


def _country_code(value: str) -> str:
    """ISO-3166 alpha-2 from a code or common country name; never blindly truncate ("United Kingdom" != "UN")."""
    v = value.strip()
    if len(v) == 2 and v.isalpha():
        return v.upper()
    return COUNTRY_NAMES.get(v.lower(), "")


class CsvImportAdapter(Adapter):
    name = SOURCE
    label = "CSV import (your own data)"
    supports_search = False

    def status(self) -> dict:
        return {"source": self.name, "label": self.label, "status": "available", "simulated": False,
                "detail": f"Upload a CSV with columns: {', '.join(COLUMNS)}"}

    def parse(self, data: bytes, filename: str | None = None) -> SearchResult:
        if len(data) > MAX_BYTES:
            raise AdapterError(f"CSV exceeds {MAX_BYTES // 1024} KB")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as e:
            raise AdapterError("CSV must be UTF-8 encoded") from e
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise AdapterError("CSV has no header row")
        header = {h: ALIASES.get(h.strip().lower(), h.strip().lower()) for h in reader.fieldnames if h}
        if "name" not in header.values():
            raise AdapterError("CSV must contain a 'name' column")
        records = []
        for i, row in enumerate(reader, start=2):
            if len(records) >= MAX_ROWS:
                raise AdapterError(f"CSV exceeds {MAX_ROWS} rows")
            f = {}
            for raw_key, col in header.items():
                v = (row.get(raw_key) or "").strip()
                if col in COLUMNS and v:
                    f[col] = v[:500]
            if not f.get("name"):
                continue
            if f.get("country"):
                code = _country_code(f["country"])
                if code:
                    f["country"] = code
                else:
                    f.pop("country")
            records.append(RawBusiness(fields=f, source_ref=f"{filename or 'upload.csv'}#row{i}"))
        return SearchResult(records=records, requests_made=0)
