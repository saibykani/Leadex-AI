import os
import uuid

os.environ.setdefault("APP_ENV", "test")
# Postgres runs: TEST_DATABASE_URL = restricted app role (leadex_app), TEST_MIGRATION_DATABASE_URL = schema owner.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///./test_leadex_{os.getpid()}.db")
os.environ["MIGRATION_DATABASE_URL"] = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
os.environ["REDIS_URL"] = ""
os.environ["JWT_SECRET"] = "test-secret-" + "x" * 32

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.core.ratelimit import limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.identity.rbac import seed_rbac  # noqa: E402

IS_PG = engine.dialect.name == "postgresql"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    if IS_PG:
        from alembic import command
        from alembic.config import Config

        cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
        command.downgrade(cfg, "base") if _has_tables() else None
        command.upgrade(cfg, "head")
    else:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            seed_rbac(db)
    yield
    engine.dispose()


def _has_tables() -> bool:
    from sqlalchemy import create_engine, inspect

    from app.core.config import get_settings

    owner = create_engine(get_settings().effective_migration_url)
    try:
        return "alembic_version" in inspect(owner).get_table_names()
    finally:
        owner.dispose()


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()


def pytest_configure(config):
    config.addinivalue_line("markers", "plan_limits: run with real Free Trial plan limits (no test upgrade)")


@pytest.fixture(autouse=True)
def _upgraded_test_plan(request, monkeypatch):
    """Most tests create many rows and would hit Free Trial limits (2 users, 1 website, ...). Treat every
    free-trial test org as being on the unlimited White Label plan. Production enforcement is unchanged;
    billing tests and tests marked `plan_limits` use the real plans."""
    if request.module.__name__.endswith("test_billing") or request.node.get_closest_marker("plan_limits"):
        yield
        return
    from app.modules.billing import service as billing

    real_plan_of = billing.plan_of

    def plan_of(db, sub):
        plan = real_plan_of(db, sub)
        return billing.get_plan(db, "white_label") if plan is not None and plan.code == "free_trial" else plan

    monkeypatch.setattr(billing, "plan_of", plan_of)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def register(client, org="Acme Realty", password="Sup3rSecretPw"):  # noqa: S107 (test fixture)
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "full_name": "Test User", "organization_name": org, "country_code": "in",
    })
    assert r.status_code == 201, r.text
    tokens = r.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers).json()
    org_id = me["memberships"][0]["organization"]["id"]
    return {"email": email, "password": password, "tokens": tokens, "headers": headers, "org_id": org_id}


def tenant_headers(account, org_id=None):
    return {**account["headers"], "X-Organization-Id": org_id or account["org_id"]}


def pytest_unconfigure(config):
    """Remove this run's SQLite file (per-process name) so runs don't accumulate test databases."""
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("sqlite:///./test_leadex_"):
        from app.core.db import engine

        engine.dispose()
        try:
            os.remove(url.removeprefix("sqlite:///"))
        except OSError:
            pass
