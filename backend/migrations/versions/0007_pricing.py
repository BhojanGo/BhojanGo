"""P8 pricing: order pricing snapshots, promotion spend; map pins on addresses.

Revision ID: 0007_pricing
Revises: 0006_rules
Create Date: 2026-11-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0007_pricing'
down_revision: Union[str, None] = '0006_rules'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('order_pricing_snapshots',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('order_id', sa.UUID(), nullable=False),
    sa.Column('quote_id', sa.UUID(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('total', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('lines', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('rule_versions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('split', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('order_id'),
    sa.UniqueConstraint('quote_id')
    )
    op.create_table('promotion_spend',
    sa.Column('rule_key', sa.UUID(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('spent', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('orders', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('rule_key')
    )
    op.add_column('addresses', sa.Column('lat', sa.Float(), nullable=True))
    op.add_column('addresses', sa.Column('lng', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('addresses', 'lng')
    op.drop_column('addresses', 'lat')
    op.drop_table('promotion_spend')
    op.drop_table('order_pricing_snapshots')
