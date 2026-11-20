# Seed data

There are no seed scripts in this directory, intentionally.

- **RBAC is seeded by migration `0001`** (`apps/api/alembic/versions/0001_identity.py`) from the role and permission definitions in `apps/api/app/modules/identity/rbac.py`. Running `alembic upgrade head` (or `infrastructure/scripts/migrate.*`) is all that is needed. Changing roles or permissions requires a new migration, so every environment stays consistent.
- **No fake business data is seeded, by design.** Leads, companies, contacts and campaigns must come from real sources or user input. When an integration is not configured, adapters report `not_configured` or return clearly labelled simulated results instead of filling the database with fabricated records.

Create your first tenant and user through the API's registration endpoint (see `docs/API_SPECIFICATION.md`).

## Sample CSV for discovery import (fictional test data)

`sample_businesses.csv` contains ~25 **entirely fictional** businesses (Pune, Hyderabad, Bengaluru, Dubai, London)
for manual QA and the end-to-end suite (`apps/api/tests/e2e`). Names are invented, emails use `example.com`,
and phone numbers are in fake/reserved ranges (UK numbers use the Ofcom drama range 020 7946 0xxx). It is
never seeded automatically; upload it via Discovery → Import CSV. The `notes` column is ignored by the importer.
