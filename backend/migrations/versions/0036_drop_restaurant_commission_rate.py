"""Drop restaurants.commission_rate (R16): commission comes only from the commission rules.

The column (default 20%) was left from before the rules engine; since R15 nothing reads it.

Revision ID: 0036_drop_restaurant_commission_rate
Revises: 0035_country_legal_entity
"""
import sqlalchemy as sa
from alembic import op

revision = "0036_drop_restaurant_commission_rate"
down_revision = "0035_country_legal_entity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("restaurants", "commission_rate")


def downgrade() -> None:
    op.add_column("restaurants", sa.Column("commission_rate", sa.Numeric(5, 4), nullable=False, server_default="0.2000"))
