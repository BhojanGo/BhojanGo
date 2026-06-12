"""pain-point layer: restaurant pricing model, delivery radius, prep time

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "restaurants",
        sa.Column("pricing_model", sa.String(30), nullable=False, server_default="percentage_commission"),
    )
    op.add_column(
        "restaurants",
        sa.Column("commission_rate", sa.Numeric(5, 4), nullable=False, server_default="0.2000"),
    )
    op.add_column(
        "restaurants",
        sa.Column("flat_fee_per_order", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "restaurants",
        sa.Column("monthly_subscription_fee", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "restaurants",
        sa.Column("delivery_radius_km", sa.Numeric(6, 2), nullable=False, server_default="5.00"),
    )
    op.add_column(
        "restaurants",
        sa.Column("avg_prep_minutes", sa.Integer(), nullable=False, server_default="20"),
    )


def downgrade() -> None:
    for column in (
        "avg_prep_minutes",
        "delivery_radius_km",
        "monthly_subscription_fee",
        "flat_fee_per_order",
        "commission_rate",
        "pricing_model",
    ):
        op.drop_column("restaurants", column)
