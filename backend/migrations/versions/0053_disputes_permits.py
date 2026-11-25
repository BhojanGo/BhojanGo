"""R39: chargebacks and US food permits. Adds a table and columns; writes no data.

* payment_disputes: Stripe charge.dispute.* (payments/service/disputes.py): the hold on the restaurant's
  payout while a dispute is open, and who bore the loss when it closed.
* restaurants.food_permit_*: the health-district food permit (number, expiry, upload, admin review, the
  30-day reminder), required where a country's Markets setting food_permit_required is on.

Revision ID: 0053_disputes_permits
Revises: 0052_offer_budget_returns
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0053_disputes_permits"
down_revision = "0052_offer_budget_returns"
branch_labels = None
depends_on = None

PERMIT = [
    ("food_permit_number", sa.String(length=40)),
    ("food_permit_expires_on", sa.Date()),
    ("food_permit_document_key", sa.String(length=300)),
    ("food_permit_status", sa.String(length=12)),
    ("food_permit_note", sa.String(length=300)),
    ("food_permit_reviewed_by", postgresql.UUID(as_uuid=True)),
    ("food_permit_reviewed_at", sa.DateTime(timezone=True)),
    ("food_permit_reminded_for", sa.Date()),
]


def upgrade() -> None:
    op.create_table(
        "payment_disputes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_dispute_id", sa.String(length=255), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("market_city", sa.String(length=20), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("outcome", sa.String(length=10), nullable=True),
        sa.Column("held", sa.Integer(), nullable=False),
        sa.Column("restaurant_loss", sa.Integer(), nullable=False),
        sa.Column("platform_loss", sa.Integer(), nullable=False),
        sa.Column("loss_bearer", sa.String(length=12), nullable=True),
        sa.Column("hold_statement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("settle_statement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_due_by", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_dispute_id"),
    )
    op.create_index("ix_payment_disputes_order_id", "payment_disputes", ["order_id"])
    op.create_index("ix_payment_disputes_restaurant_id", "payment_disputes", ["restaurant_id"])
    op.create_index("ix_payment_disputes_status", "payment_disputes", ["status"])
    for name, kind in PERMIT:
        op.add_column("restaurants", sa.Column(name, kind, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(PERMIT):
        op.drop_column("restaurants", name)
    op.drop_table("payment_disputes")
