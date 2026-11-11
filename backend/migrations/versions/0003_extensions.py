"""Create the PostgreSQL extensions the platform relies on.

Locally, infra/docker/db/init.sql already creates them. Amazon RDS has no
init script, so the first `alembic upgrade head` in staging/prod creates them
here (the RDS master user has rds_superuser, which may CREATE EXTENSION):

- postgis   — zones and distances (P6 markets, ADR-009 search)
- pg_trgm   — typo-tolerant catalog search (ADR-009)
- uuid-ossp — uuid helpers

IF NOT EXISTS makes this a no-op where they already exist. Downgrade leaves
them in place: dropping PostGIS would drop every column that uses it.

Revision ID: 0003_extensions
Revises: 0002_model_drift
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_extensions"
down_revision: Union[str, None] = "0002_model_drift"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EXTENSIONS = ("postgis", "pg_trgm", "uuid-ossp")


def upgrade() -> None:
    for name in EXTENSIONS:
        op.execute(f'CREATE EXTENSION IF NOT EXISTS "{name}"')


def downgrade() -> None:
    pass
