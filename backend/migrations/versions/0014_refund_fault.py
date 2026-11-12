"""Phase 1 decision: item refunds carry a fault (restaurant | delivery | goodwill)
that decides who pays; the refund_cost business rule it replaces is retired.

Existing item refunds were all charged to the restaurant (the old default), so
they become restaurant-fault refunds.

Revision ID: 0014_refund_fault
Revises: 0013_notifications
Create Date: 2026-11-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0014_refund_fault'
down_revision: Union[str, None] = '0013_notifications'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('refunds', sa.Column('fault', sa.String(length=12), nullable=True))
    op.execute("UPDATE refunds SET fault = 'restaurant' WHERE kind = 'items'")
    # The fault on each refund now decides who pays; stop the old rule applying.
    op.execute("UPDATE rules SET status = 'superseded', effective_to = coalesce(effective_to, now()) "
               "WHERE family = 'business' AND template = 'refund_cost' AND status IN ('published', 'draft', 'pending_approval')")


def downgrade() -> None:
    op.drop_column('refunds', 'fault')
