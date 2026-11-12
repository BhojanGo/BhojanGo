"""P11 order flow: payment-first states and deadlines on orders, the transactional
outbox, processed webhook events (idempotent webhooks).

Data: old statuses map to the new ones (pending -> pending_payment,
confirmed -> accepted, ready_for_pickup -> ready), and back on downgrade.

Revision ID: 0009_order_flow
Revises: 0008_menu_hours
Create Date: 2026-11-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0009_order_flow'
down_revision: Union[str, None] = '0008_menu_hours'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STATUS_MAP = {"pending": "pending_payment", "confirmed": "accepted", "ready_for_pickup": "ready"}


def upgrade() -> None:
    op.create_table('outbox_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('event_type', sa.String(length=60), nullable=False),
    sa.Column('aggregate_type', sa.String(length=30), nullable=False),
    sa.Column('aggregate_id', sa.String(length=64), nullable=False),
    sa.Column('envelope', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_outbox_events_aggregate_id'), 'outbox_events', ['aggregate_id'], unique=False)
    op.create_index('ix_outbox_unpublished', 'outbox_events', ['created_at'], unique=False, postgresql_where='published_at IS NULL')
    op.create_table('processed_webhook_events',
    sa.Column('provider', sa.String(length=20), nullable=False),
    sa.Column('event_id', sa.String(length=255), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('provider', 'event_id')
    )
    op.add_column('orders', sa.Column('market_city', sa.String(length=20), nullable=True))
    op.add_column('orders', sa.Column('zone_id', sa.UUID(), nullable=True))
    op.add_column('orders', sa.Column('payment_due_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('accept_due_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('placed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('picked_up_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('cancelled_by', sa.String(length=20), nullable=True))
    op.create_index(op.f('ix_orders_market_city'), 'orders', ['market_city'], unique=False)
    for old, new in STATUS_MAP.items():
        op.execute(sa.text("UPDATE orders SET status = :new WHERE status = :old").bindparams(old=old, new=new))


def downgrade() -> None:
    for old, new in STATUS_MAP.items():
        op.execute(sa.text("UPDATE orders SET status = :old WHERE status = :new").bindparams(old=old, new=new))
    op.execute("UPDATE orders SET status = 'pending' WHERE status = 'placed'")
    op.drop_index(op.f('ix_orders_market_city'), table_name='orders')
    op.drop_column('orders', 'cancelled_by')
    op.drop_column('orders', 'cancelled_at')
    op.drop_column('orders', 'picked_up_at')
    op.drop_column('orders', 'placed_at')
    op.drop_column('orders', 'accept_due_at')
    op.drop_column('orders', 'payment_due_at')
    op.drop_column('orders', 'zone_id')
    op.drop_column('orders', 'market_city')
    op.drop_table('processed_webhook_events')
    op.drop_index('ix_outbox_unpublished', table_name='outbox_events', postgresql_where='published_at IS NULL')
    op.drop_index(op.f('ix_outbox_events_aggregate_id'), table_name='outbox_events')
    op.drop_table('outbox_events')
