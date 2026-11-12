"""P13 payouts: payee payout accounts, weekly payout runs and statements; outbox
events ordered by clock_timestamp().

Revision ID: 0011_payouts
Revises: 0010_payments_refunds
Create Date: 2026-11-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0011_payouts'
down_revision: Union[str, None] = '0010_payments_refunds'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Outbox events from one transaction keep their order (now() is the same for all of them).
    op.alter_column("outbox_events", "created_at", server_default=sa.text("clock_timestamp()"))
    op.create_table('payout_accounts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('payee_type', sa.String(length=12), nullable=False),
    sa.Column('payee_id', sa.UUID(), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=False),
    sa.Column('external_id', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('country', sa.String(length=2), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('payee_type', 'payee_id', 'provider', name='uq_payout_accounts_payee')
    )
    op.create_index(op.f('ix_payout_accounts_payee_id'), 'payout_accounts', ['payee_id'], unique=False)
    op.create_table('payout_runs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('country', sa.String(length=2), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('period_start', sa.Date(), nullable=False),
    sa.Column('period_end', sa.Date(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('totals', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('approved_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('country', 'period_start', 'period_end', name='uq_payout_runs_period')
    )
    op.create_table('payout_statements',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('payee_type', sa.String(length=12), nullable=False),
    sa.Column('payee_id', sa.UUID(), nullable=False),
    sa.Column('payee_name', sa.String(length=255), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('lines', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('transfer_id', sa.String(length=255), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_payout_statements_payee', 'payout_statements', ['payee_type', 'payee_id'], unique=False)
    op.create_index(op.f('ix_payout_statements_run_id'), 'payout_statements', ['run_id'], unique=False)


def downgrade() -> None:
    op.alter_column("outbox_events", "created_at", server_default=sa.text("now()"))
    op.drop_index(op.f('ix_payout_statements_run_id'), table_name='payout_statements')
    op.drop_index('ix_payout_statements_payee', table_name='payout_statements')
    op.drop_table('payout_statements')
    op.drop_table('payout_runs')
    op.drop_index(op.f('ix_payout_accounts_payee_id'), table_name='payout_accounts')
    op.drop_table('payout_accounts')
