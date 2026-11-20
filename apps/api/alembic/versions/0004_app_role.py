"""Least-privilege runtime role so row-level security is enforced

The schema owner / superuser bypasses RLS. The API therefore connects as `leadex_app`
(NOSUPERUSER, NOBYPASSRLS) with DML-only grants. Append-only tables get INSERT/SELECT only.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
from app.core.config import get_settings

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

ROLE = "leadex_app"
APPEND_ONLY = ("audit_logs", "lead_activities")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    pw = get_settings().app_db_password.replace("'", "''")
    op.execute(
        f"""DO $$ BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{ROLE}') THEN
            CREATE ROLE {ROLE} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD '{pw}';
          ELSE
            ALTER ROLE {ROLE} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{pw}';
          END IF;
        END $$;"""
    )
    db = bind.exec_driver_sql("SELECT current_database()").scalar()
    op.execute(f'GRANT CONNECT ON DATABASE "{db}" TO {ROLE}')
    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {ROLE}")
    op.execute(f"REVOKE ALL ON alembic_version FROM {ROLE}")
    for t in APPEND_ONLY:
        op.execute(f"REVOKE UPDATE, DELETE ON {t} FROM {ROLE}")
    # Tables created by future migrations inherit DML grants.
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {ROLE}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {ROLE}")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    # The role is cluster-wide and may serve other databases, so it is not dropped.
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {ROLE}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {ROLE}")
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {ROLE}")
    op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {ROLE}")
