"""Payout providers per country from Markets: countries.payout_provider
(stripe_connect, razorpay_route, fake or none). Until now the code picked Stripe
Connect for the US and Razorpay Route for everyone else; existing rows keep what
they had for the two countries that pay out today, every other country starts at
"none" (it can't open until an admin picks a provider in Markets).

Revision ID: 0027_country_payout_provider
Revises: 0026_waitlist_web
"""
import sqlalchemy as sa
from alembic import op

revision = "0027_country_payout_provider"
down_revision = "0026_waitlist_web"
branch_labels = None
depends_on = None

# What get_payout_provider() hard-coded before this migration (the integration test runs these).
BACKFILL = (
    "UPDATE countries SET payout_provider = 'razorpay_route' WHERE code = 'IN'",
    "UPDATE countries SET payout_provider = 'stripe_connect' WHERE code = 'US'",
)


def upgrade() -> None:
    op.add_column("countries", sa.Column("payout_provider", sa.String(20), nullable=False, server_default="none"))
    for sql in BACKFILL:
        op.execute(sql)


def downgrade() -> None:
    op.drop_column("countries", "payout_provider")
