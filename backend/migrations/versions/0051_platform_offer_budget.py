"""R37: BhojanGo-funded offers spend from a monthly budget (pricing/service/offer_budget.py).

Adds one table, platform_offer_spend: spend per budget pool and month. The budget itself is a Markets
setting (platform_offer_budget), so no column is added to markets. No data is written: with no budget
set, BhojanGo-funded offers simply stop applying.

Revision ID: 0051_platform_offer_budget
Revises: 0050_no_zone_minimum
"""
import sqlalchemy as sa
from alembic import op

revision = "0051_platform_offer_budget"
down_revision = "0050_no_zone_minimum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_offer_spend",
        sa.Column("pool", sa.String(length=40), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("spent", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("orders", sa.Integer(), nullable=False),
        sa.Column("alerted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("pool", "month"),
    )


def downgrade() -> None:
    op.drop_table("platform_offer_spend")
