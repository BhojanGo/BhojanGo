"""Bring the schema in line with the models.

The pre-P1 per-service migrations never created some things the models (and
the code) rely on, so on any migrated database /api/v1/me/addresses and the
catalog reads that filter on deleted_at returned 500. 0001_baseline kept that
old schema on purpose; this revision closes the gap:

- addresses table (identity) and ix_addresses_user_id
- restaurants.deleted_at, menu_items.deleted_at (catalog soft delete)
- ix_payment_intents_status (payments)
- users.email/phone, restaurants.slug, wallets.user_id and
  payment_intents.idempotency_key: unique constraint + plain index become
  the single unique index the models declare (same uniqueness, swapped in
  one transaction)

After this revision `alembic check` reports no differences; CI enforces that.

Revision ID: 0002_model_drift
Revises: 0001_baseline
Create Date: 2026-11-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_model_drift"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('addresses',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('label', sa.String(length=50), nullable=False),
    sa.Column('street', sa.String(length=500), nullable=False),
    sa.Column('city', sa.String(length=100), nullable=False),
    sa.Column('state', sa.String(length=100), nullable=False),
    sa.Column('postal_code', sa.String(length=20), nullable=False),
    sa.Column('country', sa.String(length=2), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_addresses_user_id'), 'addresses', ['user_id'], unique=False)
    op.add_column('menu_items', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint(op.f('payment_intents_idempotency_key_key'), 'payment_intents', type_='unique')
    op.create_index(op.f('ix_payment_intents_idempotency_key'), 'payment_intents', ['idempotency_key'], unique=True)
    op.create_index(op.f('ix_payment_intents_status'), 'payment_intents', ['status'], unique=False)
    op.add_column('restaurants', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint(op.f('restaurants_slug_key'), 'restaurants', type_='unique')
    op.drop_index(op.f('ix_restaurants_slug'), table_name='restaurants')
    op.create_index(op.f('ix_restaurants_slug'), 'restaurants', ['slug'], unique=True)
    op.drop_constraint(op.f('users_email_key'), 'users', type_='unique')
    op.drop_constraint(op.f('users_phone_key'), 'users', type_='unique')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.drop_index(op.f('ix_users_phone'), table_name='users')
    op.create_index(op.f('ix_users_phone'), 'users', ['phone'], unique=True)
    op.drop_constraint(op.f('wallets_user_id_key'), 'wallets', type_='unique')
    op.drop_index(op.f('ix_wallets_user_id'), table_name='wallets')
    op.create_index(op.f('ix_wallets_user_id'), 'wallets', ['user_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_wallets_user_id'), table_name='wallets')
    op.create_index(op.f('ix_wallets_user_id'), 'wallets', ['user_id'], unique=False)
    op.create_unique_constraint(op.f('wallets_user_id_key'), 'wallets', ['user_id'])
    op.drop_index(op.f('ix_users_phone'), table_name='users')
    op.create_index(op.f('ix_users_phone'), 'users', ['phone'], unique=False)
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)
    op.create_unique_constraint(op.f('users_phone_key'), 'users', ['phone'])
    op.create_unique_constraint(op.f('users_email_key'), 'users', ['email'])
    op.drop_index(op.f('ix_restaurants_slug'), table_name='restaurants')
    op.create_index(op.f('ix_restaurants_slug'), 'restaurants', ['slug'], unique=False)
    op.create_unique_constraint(op.f('restaurants_slug_key'), 'restaurants', ['slug'])
    op.drop_column('restaurants', 'deleted_at')
    op.drop_index(op.f('ix_payment_intents_status'), table_name='payment_intents')
    op.drop_index(op.f('ix_payment_intents_idempotency_key'), table_name='payment_intents')
    op.create_unique_constraint(op.f('payment_intents_idempotency_key_key'), 'payment_intents', ['idempotency_key'])
    op.drop_column('menu_items', 'deleted_at')
    op.drop_index(op.f('ix_addresses_user_id'), table_name='addresses')
    op.drop_table('addresses')
