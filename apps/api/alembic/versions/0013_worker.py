"""worker: saved_searches.last_run_at for the Celery scheduler (guarded; 0006 already creates it)

Revision ID: 0013
Revises: 0012
"""
import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def _has_column() -> bool:
    cols = sa.inspect(op.get_bind()).get_columns("saved_searches")
    return any(c["name"] == "last_run_at" for c in cols)


def upgrade() -> None:
    if not _has_column():
        op.add_column("saved_searches", sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # The column belongs to 0006; this revision never owns it, so downgrade is a no-op.
    pass
