"""Incident tools (R17): a kitchen paused by an admin, ordering pauses, bulk refunds and bulk messages.

Revision ID: 0037_incident_tools
Revises: 0036_drop_commission_rate
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0037_incident_tools"
down_revision = "0036_drop_commission_rate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("restaurants", sa.Column("admin_paused_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("restaurants", sa.Column("admin_paused_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("restaurants", sa.Column("admin_pause_reason", sa.Text(), nullable=True))
    op.add_column("restaurants", sa.Column("admin_paused_by", pg.UUID(as_uuid=True), nullable=True))
    op.create_table(
        "ordering_pauses",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("area", sa.String(100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("note", sa.String(200), nullable=True),
        sa.Column("until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_by", pg.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_ordering_pauses_active", "ordering_pauses", ["ended_at", "scope"])
    op.create_table(
        "bulk_refunds",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("market_city", sa.String(20), nullable=False),
        sa.Column("filters", pg.JSONB(), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("orders", pg.JSONB(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("requested_by", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("decided_by", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("results", pg.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bulk_refunds_market_city", "bulk_refunds", ["market_city"])
    op.create_table(
        "bulk_messages",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("audience", pg.JSONB(), nullable=False),
        sa.Column("template", sa.String(40), nullable=False),
        sa.Column("params", pg.JSONB(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recipients", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("created_by", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bulk_messages_scope", "bulk_messages", ["scope"])


def downgrade() -> None:
    op.drop_table("bulk_messages")
    op.drop_table("bulk_refunds")
    op.drop_table("ordering_pauses")
    for c in ("admin_paused_by", "admin_pause_reason", "admin_paused_until", "admin_paused_at"):
        op.drop_column("restaurants", c)
