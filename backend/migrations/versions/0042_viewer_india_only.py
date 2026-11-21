"""The seed's read-only viewer is India's only (R27).

R26: the account the console labels "Viewer (IN)" (viewer@example.com) also held viewer at
US, so it read US Finance. The seed now gives it India only, and a separate
viewer.us@example.com reads the USA. This removes the US assignment from test environments
that were seeded before (QA); a database without that account is unchanged. Data only:
nothing is added, dropped or renamed.

Revision ID: 0042_viewer_india_only
Revises: 0041_statement_carry
"""
from alembic import op

revision = "0042_viewer_india_only"
down_revision = "0041_statement_carry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM admin_role_assignments a USING users u "
        "WHERE a.user_id = u.id AND u.email = 'viewer@example.com' AND a.role = 'viewer' AND a.scope = 'US'"
    )


def downgrade() -> None:
    pass  # the seed no longer grants it; run the seed of an older release to put it back
