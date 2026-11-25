"""R43: menu editing. Adds columns and a table; changes no existing row.

* menu_items.spice_level (0 none .. 3 hot; NULL: not said), menu_items/menu_categories.available_from and
  available_until (a dish or a category served only between two local times, e.g. breakfast 07:00-11:00).
* menu_changes: the menu's history (who, when, each field's old and new value), shown to the restaurant and admins.

Revision ID: 0055_menu_editing
Revises: 0054_payout_weeks
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0055_menu_editing"
down_revision = "0054_payout_weeks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("menu_items", sa.Column("spice_level", sa.SmallInteger(), nullable=True))
    op.create_check_constraint("ck_menu_items_spice_level", "menu_items", "spice_level BETWEEN 0 AND 3")
    for table in ("menu_items", "menu_categories"):
        op.add_column(table, sa.Column("available_from", sa.Time(), nullable=True))
        op.add_column(table, sa.Column("available_until", sa.Time(), nullable=True))
    op.create_table(
        "menu_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_name", sa.String(255), nullable=False),
        sa.Column("actor_kind", sa.String(20), nullable=False),
        sa.Column("entity", sa.String(20), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entity_name", sa.String(255), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("changes", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_menu_changes_restaurant_at", "menu_changes", ["restaurant_id", "at"])


def downgrade() -> None:
    op.drop_index("ix_menu_changes_restaurant_at", table_name="menu_changes")
    op.drop_table("menu_changes")
    for table in ("menu_categories", "menu_items"):
        op.drop_column(table, "available_until")
        op.drop_column(table, "available_from")
    op.drop_constraint("ck_menu_items_spice_level", "menu_items", type_="check")
    op.drop_column("menu_items", "spice_level")
