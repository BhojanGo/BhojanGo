"""pain-point layer: fee breakdown, readiness, distance, status timeline

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("platform_fee", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("restaurant_payout", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("estimated_prep_minutes", sa.Integer(), nullable=False, server_default="20"))
    op.add_column("orders", sa.Column("restaurant_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("actual_ready_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("delivery_distance_km", sa.Numeric(6, 2), nullable=True))
    op.add_column("orders", sa.Column("is_long_distance", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("orders", sa.Column("status_history", postgresql.JSONB(), nullable=False, server_default="[]"))


def downgrade() -> None:
    for column in (
        "status_history",
        "is_long_distance",
        "delivery_distance_km",
        "actual_ready_at",
        "restaurant_accepted_at",
        "estimated_prep_minutes",
        "restaurant_payout",
        "platform_fee",
    ):
        op.drop_column("orders", column)
