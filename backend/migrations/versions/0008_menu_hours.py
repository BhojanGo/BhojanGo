"""P10 menu modifiers and store hours: option groups, options, item links, weekly
hours and overrides, sold out today, restaurant tier, FSSAI licence and pause reason.

Data: each item's JSON ``customizations`` becomes option groups, then the column
is dropped (downgrade rebuilds the JSON from the groups).

Revision ID: 0008_menu_hours
Revises: 0007_pricing
Create Date: 2026-11-12

"""
from typing import Sequence, Union

import json
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0008_menu_hours'
down_revision: Union[str, None] = '0007_pricing'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('option_groups',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('restaurant_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('min_picks', sa.SmallInteger(), nullable=False),
    sa.Column('max_picks', sa.SmallInteger(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('min_picks >= 0 AND max_picks >= 1 AND min_picks <= max_picks', name='ck_option_groups_picks'),
    sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_option_groups_restaurant_id'), 'option_groups', ['restaurant_id'], unique=False)
    op.create_table('store_hour_overrides',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('restaurant_id', sa.UUID(), nullable=False),
    sa.Column('day', sa.Date(), nullable=False),
    sa.Column('closed', sa.Boolean(), nullable=False),
    sa.Column('opens', sa.Time(), nullable=True),
    sa.Column('closes', sa.Time(), nullable=True),
    sa.Column('note', sa.String(length=120), nullable=True),
    sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('restaurant_id', 'day', name='uq_store_hour_overrides_day')
    )
    op.create_index(op.f('ix_store_hour_overrides_restaurant_id'), 'store_hour_overrides', ['restaurant_id'], unique=False)
    op.create_table('store_hours',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('restaurant_id', sa.UUID(), nullable=False),
    sa.Column('weekday', sa.SmallInteger(), nullable=False),
    sa.Column('opens', sa.Time(), nullable=False),
    sa.Column('closes', sa.Time(), nullable=False),
    sa.CheckConstraint('weekday BETWEEN 0 AND 6', name='ck_store_hours_weekday'),
    sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_store_hours_restaurant_id'), 'store_hours', ['restaurant_id'], unique=False)
    op.create_table('options',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('group_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('is_available', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['option_groups.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_options_group_id'), 'options', ['group_id'], unique=False)
    op.create_table('menu_item_option_groups',
    sa.Column('menu_item_id', sa.UUID(), nullable=False),
    sa.Column('group_id', sa.UUID(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['option_groups.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('menu_item_id', 'group_id')
    )
    op.create_index(op.f('ix_menu_item_option_groups_group_id'), 'menu_item_option_groups', ['group_id'], unique=False)
    op.add_column('menu_items', sa.Column('sold_out_until', sa.DateTime(timezone=True), nullable=True))
    _customizations_to_groups()
    op.drop_column('menu_items', 'customizations')
    op.add_column('restaurants', sa.Column('tier', sa.String(length=1), nullable=True))
    op.add_column('restaurants', sa.Column('fssai_number', sa.String(length=14), nullable=True))
    op.add_column('restaurants', sa.Column('fssai_expires_on', sa.Date(), nullable=True))
    op.add_column('restaurants', sa.Column('paused_reason', sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.add_column('menu_items', sa.Column('customizations', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), autoincrement=False, nullable=False))
    _groups_to_customizations()
    op.drop_column('restaurants', 'paused_reason')
    op.drop_column('restaurants', 'fssai_expires_on')
    op.drop_column('restaurants', 'fssai_number')
    op.drop_column('restaurants', 'tier')
    op.drop_column('menu_items', 'sold_out_until')
    op.drop_index(op.f('ix_menu_item_option_groups_group_id'), table_name='menu_item_option_groups')
    op.drop_table('menu_item_option_groups')
    op.drop_index(op.f('ix_options_group_id'), table_name='options')
    op.drop_table('options')
    op.drop_index(op.f('ix_store_hours_restaurant_id'), table_name='store_hours')
    op.drop_table('store_hours')
    op.drop_index(op.f('ix_store_hour_overrides_restaurant_id'), table_name='store_hour_overrides')
    op.drop_table('store_hour_overrides')
    op.drop_index(op.f('ix_option_groups_restaurant_id'), table_name='option_groups')
    op.drop_table('option_groups')


def _customizations_to_groups() -> None:
    """One option group per item customization (min_picks 1 if it was required)."""
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, restaurant_id, customizations FROM menu_items WHERE customizations <> '[]'::jsonb")).all()
    for item_id, restaurant_id, customizations in rows:
        for i, c in enumerate(customizations or []):
            gid = uuid.uuid4()
            max_picks = max(1, int(c.get("max", 1)))
            conn.execute(sa.text(
                "INSERT INTO option_groups (id, restaurant_id, name, min_picks, max_picks, sort_order) "
                "VALUES (:id, :rid, :name, :min, :max, :sort)"),
                {"id": gid, "rid": restaurant_id, "name": c.get("name", "Options")[:80],
                 "min": 1 if c.get("required") else 0, "max": max_picks, "sort": i})
            for j, o in enumerate(c.get("options", [])):
                conn.execute(sa.text(
                    "INSERT INTO options (id, group_id, name, price, is_default, is_available, sort_order) "
                    "VALUES (:id, :gid, :name, :price, false, true, :sort)"),
                    {"id": uuid.uuid4(), "gid": gid, "name": o.get("name", "")[:80], "price": o.get("price", 0), "sort": j})
            conn.execute(sa.text(
                "INSERT INTO menu_item_option_groups (menu_item_id, group_id, sort_order) VALUES (:item, :gid, :sort)"),
                {"item": item_id, "gid": gid, "sort": i})


def _groups_to_customizations() -> None:
    conn = op.get_bind()
    links = conn.execute(sa.text(
        "SELECT l.menu_item_id, g.id, g.name, g.min_picks, g.max_picks FROM menu_item_option_groups l "
        "JOIN option_groups g ON g.id = l.group_id ORDER BY l.menu_item_id, l.sort_order")).all()
    by_item: dict = {}
    for item_id, gid, name, min_picks, max_picks in links:
        opts = conn.execute(sa.text("SELECT name, price FROM options WHERE group_id = :g ORDER BY sort_order"), {"g": gid}).all()
        by_item.setdefault(item_id, []).append({
            "name": name, "required": min_picks > 0, "max": max_picks,
            "options": [{"name": n, "price": float(p)} for n, p in opts]})
    for item_id, custom in by_item.items():
        conn.execute(sa.text("UPDATE menu_items SET customizations = CAST(:c AS jsonb) WHERE id = :id"),
                     {"c": json.dumps(custom), "id": item_id})
