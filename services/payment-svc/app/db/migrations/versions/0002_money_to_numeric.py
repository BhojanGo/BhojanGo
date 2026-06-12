"""wallet money -> numeric(12,2); add payment_intents.refunded_amount

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-03 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MONEY_COLUMNS = [
    ("wallets", "balance"),
    ("wallet_transactions", "amount"),
    ("wallet_transactions", "balance_after"),
]


def upgrade() -> None:
    for table, column in _MONEY_COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.Numeric(12, 2),
            existing_type=sa.Float(),
            existing_nullable=False,
            postgresql_using=f"{column}::numeric(12,2)",
        )
    op.add_column(
        "payment_intents",
        sa.Column("refunded_amount", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("payment_intents", "refunded_amount")
    for table, column in _MONEY_COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.Float(),
            existing_type=sa.Numeric(12, 2),
            existing_nullable=False,
            postgresql_using=f"{column}::double precision",
        )
