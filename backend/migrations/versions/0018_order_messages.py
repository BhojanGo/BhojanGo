"""B2: quick messages between the customer and the rider during an order.

Revision ID: 0018_order_messages
Revises: 0017_partner_app
Create Date: 2026-11-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0018_order_messages'
down_revision: Union[str, None] = '0017_partner_app'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'order_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sender_role', sa.String(length=10), nullable=False),
        sa.Column('preset', sa.String(length=30), nullable=True),
        sa.Column('text', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_order_messages_order', 'order_messages', ['order_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_order_messages_order', table_name='order_messages')
    op.drop_table('order_messages')
