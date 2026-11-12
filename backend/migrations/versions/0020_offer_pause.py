"""B4: admins can pause a kitchen's own offer (which goes live without approval).

Revision ID: 0020_offer_pause
Revises: 0019_support_tickets
Create Date: 2026-11-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0020_offer_pause'
down_revision: Union[str, None] = '0019_support_tickets'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rules', sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('rules', sa.Column('paused_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('rules', sa.Column('paused_reason', sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column('rules', 'paused_reason')
    op.drop_column('rules', 'paused_by')
    op.drop_column('rules', 'paused_at')
