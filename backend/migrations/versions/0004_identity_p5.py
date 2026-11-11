"""P5 identity: admin role assignments; email optional (phone sign-up).

Revision ID: 0004_identity_p5
Revises: 0003_extensions
Create Date: 2026-11-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_identity_p5"
down_revision: Union[str, None] = "0003_extensions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "email", existing_type=sa.String(255), nullable=True)
    op.create_table(
        "admin_role_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "role", "scope", name="uq_admin_role_assignment"),
    )
    op.create_index("ix_admin_role_assignments_user_id", "admin_role_assignments", ["user_id"])
    op.create_index("ix_admin_role_assignments_scope", "admin_role_assignments", ["scope"])


def downgrade() -> None:
    op.drop_table("admin_role_assignments")
    # Phone-only accounts get a placeholder so the NOT NULL constraint can return.
    op.execute("UPDATE users SET email = 'phone_' || id || '@users.bhojango.invalid' WHERE email IS NULL")
    op.alter_column("users", "email", existing_type=sa.String(255), nullable=False)
