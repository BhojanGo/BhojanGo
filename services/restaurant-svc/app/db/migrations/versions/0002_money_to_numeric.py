"""convert money columns from float to numeric(12,2)

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

# (table, column) money columns moving Float -> Numeric(12, 2)
_MONEY_COLUMNS = [
    ("menu_items", "price"),
    ("restaurants", "minimum_order_amount"),
    ("restaurants", "delivery_fee"),
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


def downgrade() -> None:
    for table, column in _MONEY_COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.Float(),
            existing_type=sa.Numeric(12, 2),
            existing_nullable=False,
            postgresql_using=f"{column}::double precision",
        )
