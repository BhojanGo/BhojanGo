"""P17: "Tell me when you launch" sign-ups from outside served areas.

Revision ID: 0015_launch_waitlist
Revises: 0014_refund_fault
Create Date: 2026-11-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0015_launch_waitlist'
down_revision: Union[str, None] = '0014_refund_fault'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'launch_waitlist',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lng', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phone', name='uq_launch_waitlist_phone'),
    )


def downgrade() -> None:
    op.drop_table('launch_waitlist')
