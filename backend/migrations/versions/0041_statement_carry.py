"""Negative kitchen statements are carried, never written off (R23).

A kitchen's week can net below zero (refunds it caused in a week with few sales, offers it
funded). Until now the payout run marked such a statement paid ("nothing to send"), so the
balance was lost. Now the balance is carried into the kitchen's next statement as "Carried
from last week" and nothing is paid until it is covered; the kitchen is never charged.

payout_statements gains (columns only; nothing is dropped or renamed):
  carried_in      minor units, <= 0: the balance brought from earlier statements
  carried_to      the statement this one's negative balance was carried into (set once)
  negative_weeks  the payee's weeks below zero in a row, this one included
  negative_since  the Monday of the first of those weeks

Revision ID: 0041_statement_carry
Revises: 0040_cache_versions
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0041_statement_carry"
down_revision = "0040_cache_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payout_statements", sa.Column("carried_in", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("payout_statements", sa.Column("carried_to", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("payout_statements", sa.Column("negative_weeks", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("payout_statements", sa.Column("negative_since", sa.Date(), nullable=True))
    op.create_index("ix_payout_statements_carried_to", "payout_statements", ["carried_to"])


def downgrade() -> None:
    op.drop_index("ix_payout_statements_carried_to", table_name="payout_statements")
    op.drop_column("payout_statements", "negative_since")
    op.drop_column("payout_statements", "negative_weeks")
    op.drop_column("payout_statements", "carried_to")
    op.drop_column("payout_statements", "carried_in")
