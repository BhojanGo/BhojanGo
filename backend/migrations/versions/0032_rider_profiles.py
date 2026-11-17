"""Delivery partner sign-up details (R9): date of birth and vehicle.

rider_profiles: one row per delivery partner, written by POST /riders/apply after
the country's minimum age and allowed vehicles are checked. A new table only;
delivery partners who signed up before have no row (nothing reads it as required).

Revision ID: 0032_rider_profiles
Revises: 0031_legal_documents
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0032_rider_profiles"
down_revision = "0031_legal_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rider_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("vehicle", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("rider_profiles")
