"""Report or block in quick messages (R19, Apple 1.2): chat_blocks, one row per pair of
users (who blocked whom). Reports are support tickets of kind "chat_report" (no new table).

Revision ID: 0038_chat_reports
Revises: 0037_incident_tools
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0038_chat_reports"
down_revision = "0037_incident_tools"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_blocks",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("blocker_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("blocked_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_chat_blocks_pair"),
    )
    op.create_index("ix_chat_blocks_blocker_id", "chat_blocks", ["blocker_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_blocks_blocker_id", table_name="chat_blocks")
    op.drop_table("chat_blocks")
