"""convert order money columns from float to numeric(12,2)

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

_MONEY_COLUMNS = ["subtotal", "delivery_fee", "taxes", "tip", "discount", "total"]


def upgrade() -> None:
    for column in _MONEY_COLUMNS:
        op.alter_column(
            "orders",
            column,
            type_=sa.Numeric(12, 2),
            existing_type=sa.Float(),
            existing_nullable=False,
            postgresql_using=f"{column}::numeric(12,2)",
        )


def downgrade() -> None:
    for column in _MONEY_COLUMNS:
        op.alter_column(
            "orders",
            column,
            type_=sa.Float(),
            existing_type=sa.Numeric(12, 2),
            existing_nullable=False,
            postgresql_using=f"{column}::double precision",
        )
