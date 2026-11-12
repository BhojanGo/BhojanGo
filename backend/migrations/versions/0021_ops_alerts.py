"""P23: alerts from Prometheus/Alertmanager, shown in the admin console.

Revision ID: 0021_ops_alerts
Revises: 0020_offer_pause
Create Date: 2026-11-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0021_ops_alerts'
down_revision: Union[str, None] = '0020_offer_pause'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ops_alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fingerprint', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('city', sa.String(length=20), nullable=True),
        sa.Column('summary', sa.String(length=300), nullable=False),
        sa.Column('description', sa.String(length=1000), nullable=True),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fingerprint'),
    )
    op.create_index('ix_ops_alerts_city', 'ops_alerts', ['city'])


def downgrade() -> None:
    op.drop_index('ix_ops_alerts_city', table_name='ops_alerts')
    op.drop_table('ops_alerts')
