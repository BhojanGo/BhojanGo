"""A state's short code (regions.short_code): "Boise, ID", "Hyderabad, TG" in the location line.

Existing states get the second part of their ISO 3166-2 code (US-ID -> ID, IN-TG -> TG).

Revision ID: 0039_region_short_code
Revises: 0038_chat_reports
"""
import sqlalchemy as sa
from alembic import op

revision = "0039_region_short_code"
down_revision = "0038_chat_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("regions", sa.Column("short_code", sa.String(10), nullable=True))
    op.execute("UPDATE regions SET short_code = upper(split_part(code, '-', 2)) WHERE short_code IS NULL")


def downgrade() -> None:
    op.drop_column("regions", "short_code")
