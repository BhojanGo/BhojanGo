"""B3/B5: support tickets (kitchen call-back requests, customer problem reports).

Revision ID: 0019_support_tickets
Revises: 0018_order_messages
Create Date: 2026-11-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0019_support_tickets'
down_revision: Union[str, None] = '0018_order_messages'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'support_tickets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=12), nullable=False),
        sa.Column('market_city', sa.String(length=20), nullable=True),
        sa.Column('country', sa.String(length=2), nullable=False),
        sa.Column('requester_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('requester_role', sa.String(length=20), nullable=False),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('topic', sa.String(length=40), nullable=False),
        sa.Column('note', sa.String(length=500), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolution', sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_support_tickets_open', 'support_tickets', ['status', 'market_city', 'created_at'])
    op.create_index('ix_support_tickets_requester_id', 'support_tickets', ['requester_id'])
    op.create_index('ix_support_tickets_restaurant_id', 'support_tickets', ['restaurant_id'])
    op.create_index('ix_support_tickets_order_id', 'support_tickets', ['order_id'])


def downgrade() -> None:
    op.drop_index('ix_support_tickets_order_id', table_name='support_tickets')
    op.drop_index('ix_support_tickets_restaurant_id', table_name='support_tickets')
    op.drop_index('ix_support_tickets_requester_id', table_name='support_tickets')
    op.drop_index('ix_support_tickets_open', table_name='support_tickets')
    op.drop_table('support_tickets')
