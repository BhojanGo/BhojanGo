"""R38: a cancelled, unpaid or refunded order gives its BhojanGo-funded offer cost back to the budget
(pricing/service/offer_budget.py ``give_back``). One new table, platform_offer_returns: what each order
has given back, so nothing is returned twice. No data is written.

Revision ID: 0052_offer_budget_returns
Revises: 0051_platform_offer_budget
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0052_offer_budget_returns"
down_revision = "0051_platform_offer_budget"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_offer_returns",
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pool", sa.String(length=40), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("returned", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("order_id"),
    )


def downgrade() -> None:
    op.drop_table("platform_offer_returns")
