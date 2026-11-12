"""P15 notifications: push provider per device (expo | fcm | apns); one
message per event, recipient and channel (event_id), with its outcome.

Revision ID: 0013_notifications
Revises: 0012_dispatch
Create Date: 2026-11-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0013_notifications'
down_revision: Union[str, None] = '0012_dispatch'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('device_tokens', sa.Column('provider', sa.String(length=10), server_default='fcm', nullable=False))
    op.add_column('notifications', sa.Column('event_id', sa.String(length=64), nullable=True))
    op.add_column('notifications', sa.Column('status', sa.String(length=10), server_default='sent', nullable=False))
    op.add_column('notifications', sa.Column('language', sa.String(length=2), server_default='en', nullable=False))
    op.create_index('uq_notifications_event_user_channel', 'notifications', ['event_id', 'user_id', 'channel'],
                    unique=True, postgresql_where=sa.text('event_id IS NOT NULL'))


def downgrade() -> None:
    op.drop_index('uq_notifications_event_user_channel', table_name='notifications',
                  postgresql_where=sa.text('event_id IS NOT NULL'))
    op.drop_column('notifications', 'language')
    op.drop_column('notifications', 'status')
    op.drop_column('notifications', 'event_id')
    op.drop_column('device_tokens', 'provider')
