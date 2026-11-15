"""Account area for the web: default address and delivery notes, saved cards
(tokens only), favourites and notification preferences.

Existing addresses: each user's oldest address becomes their default (the
rule for new accounts: the first address is the default).

Revision ID: 0025_account_features
Revises: 0024_order_batch_position
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0025_account_features"
down_revision = "0024_order_batch_position"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("addresses", sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("addresses", sa.Column("delivery_notes", sa.String(length=500), nullable=True))
    op.execute(
        "UPDATE addresses SET is_default = true WHERE id IN ("
        " SELECT DISTINCT ON (user_id) id FROM addresses ORDER BY user_id, created_at, id)"
    )
    op.create_index("uq_addresses_one_default", "addresses", ["user_id"], unique=True,
                    postgresql_where=sa.text("is_default"))

    op.create_table(
        "payment_methods",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=10), nullable=False),
        sa.Column("provider_token", sa.String(length=255), nullable=False),
        sa.Column("brand", sa.String(length=20), nullable=False),
        sa.Column("last4", sa.String(length=4), nullable=False),
        sa.Column("exp_month", sa.SmallInteger(), nullable=False),
        sa.Column("exp_year", sa.SmallInteger(), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("provider IN ('stripe', 'razorpay', 'fake')", name="ck_payment_methods_provider"),
        sa.CheckConstraint("length(last4) = 4", name="ck_payment_methods_last4"),
        sa.CheckConstraint("exp_month BETWEEN 1 AND 12", name="ck_payment_methods_exp_month"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", "provider_token", name="uq_payment_methods_token"),
    )
    op.create_index(op.f("ix_payment_methods_user_id"), "payment_methods", ["user_id"], unique=False)
    op.create_index("uq_payment_methods_one_default", "payment_methods", ["user_id"], unique=True,
                    postgresql_where=sa.text("is_default"))

    op.create_table(
        "favourites",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('restaurant', 'item')", name="ck_favourites_kind"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "kind", "target_id"),
    )

    op.create_table(
        "notification_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=10), nullable=False),
        sa.Column("channel", sa.String(length=10), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("category IN ('orders', 'offers', 'account')", name="ck_notification_preferences_category"),
        sa.CheckConstraint("channel IN ('push', 'sms', 'email')", name="ck_notification_preferences_channel"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "category", "channel"),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_table("favourites")
    op.drop_index("uq_payment_methods_one_default", table_name="payment_methods", postgresql_where=sa.text("is_default"))
    op.drop_index(op.f("ix_payment_methods_user_id"), table_name="payment_methods")
    op.drop_table("payment_methods")
    op.drop_index("uq_addresses_one_default", table_name="addresses", postgresql_where=sa.text("is_default"))
    op.drop_column("addresses", "delivery_notes")
    op.drop_column("addresses", "is_default")
