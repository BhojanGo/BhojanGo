"""Payouts through Stripe Connect Express (R10): onboarding state and transfer status.

payout_accounts: what the provider says about the account (details submitted, payouts
enabled, what it still needs, why it is disabled, the last failed bank payout), kept
up to date from Connect webhooks (account.updated, payout.failed) and on demand.
Accounts that were already active are marked ready.

payout_statements: how many transfers were tried (the idempotency key carries it, so
a retry after a failure or a reversal is a new transfer) and when the money was sent.

Revision ID: 0034_payout_onboarding
Revises: 0032_rider_profiles
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0034_payout_onboarding"
down_revision = "0032_rider_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payout_accounts", sa.Column("details_submitted", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("payout_accounts", sa.Column("payouts_enabled", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("payout_accounts", sa.Column("requirements_due", postgresql.JSONB(), server_default="[]", nullable=False))
    op.add_column("payout_accounts", sa.Column("disabled_reason", sa.String(100), nullable=True))
    op.add_column("payout_accounts", sa.Column("payout_error", sa.Text(), nullable=True))
    op.add_column("payout_accounts", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.execute("UPDATE payout_accounts SET details_submitted = true, payouts_enabled = true WHERE status = 'active'")
    op.create_index("ix_payout_accounts_external_id", "payout_accounts", ["external_id"])
    op.add_column("payout_statements", sa.Column("attempts", sa.Integer(), server_default="0", nullable=False))
    op.add_column("payout_statements", sa.Column("transferred_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_payout_statements_transfer_id", "payout_statements", ["transfer_id"])


def downgrade() -> None:
    op.drop_index("ix_payout_statements_transfer_id", table_name="payout_statements")
    op.drop_column("payout_statements", "transferred_at")
    op.drop_column("payout_statements", "attempts")
    op.drop_index("ix_payout_accounts_external_id", table_name="payout_accounts")
    for col in ("updated_at", "payout_error", "disabled_reason", "requirements_due", "payouts_enabled", "details_submitted"):
        op.drop_column("payout_accounts", col)
