"""Tier changes for restaurants, approved by a second admin.

Revision ID: 0023_restaurant_tier_changes
Revises: 0022_commission_rate_slot
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023_restaurant_tier_changes"
down_revision = "0022_commission_rate_slot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "restaurant_tier_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_tier", sa.String(1), nullable=True),
        sa.Column("to_tier", sa.String(1), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
    )
    op.create_index("ix_restaurant_tier_changes_restaurant_id", "restaurant_tier_changes", ["restaurant_id"])


def downgrade() -> None:
    op.drop_index("ix_restaurant_tier_changes_restaurant_id", table_name="restaurant_tier_changes")
    op.drop_table("restaurant_tier_changes")
