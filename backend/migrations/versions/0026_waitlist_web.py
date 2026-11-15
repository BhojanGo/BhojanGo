"""Website "Notify me" (web v2): the launch waitlist takes an email, a city (known
or typed), consent and where the sign-up came from, as well as the apps' phone +
location. Markets shows the demand per city. Statuses gain "soon" (a string
column: no schema change).

Revision ID: 0026_waitlist_web
Revises: 0025_account_features
"""
import sqlalchemy as sa
from alembic import op

revision = "0026_waitlist_web"
down_revision = "0025_account_features"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_launch_waitlist_phone", "launch_waitlist", type_="unique")
    op.alter_column("launch_waitlist", "phone", existing_type=sa.String(20), nullable=True)
    op.alter_column("launch_waitlist", "lat", existing_type=sa.Float(), nullable=True)
    op.alter_column("launch_waitlist", "lng", existing_type=sa.Float(), nullable=True)
    op.add_column("launch_waitlist", sa.Column("email", sa.String(254), nullable=True))
    op.add_column("launch_waitlist", sa.Column("city_code", sa.String(20), nullable=True))
    op.add_column("launch_waitlist", sa.Column("city_text", sa.String(100), nullable=True))
    op.add_column("launch_waitlist", sa.Column("country", sa.String(2), nullable=True))
    op.add_column("launch_waitlist", sa.Column("locale", sa.String(10), nullable=True))
    op.add_column("launch_waitlist", sa.Column("source", sa.String(20), nullable=False, server_default="app"))
    op.add_column("launch_waitlist", sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_launch_waitlist_email", "launch_waitlist", ["email"])
    op.create_index("ix_launch_waitlist_phone", "launch_waitlist", ["phone"])
    op.create_index("ix_launch_waitlist_city_code", "launch_waitlist", ["city_code"])


def downgrade() -> None:
    op.drop_index("ix_launch_waitlist_city_code", "launch_waitlist")
    op.drop_index("ix_launch_waitlist_phone", "launch_waitlist")
    op.drop_index("ix_launch_waitlist_email", "launch_waitlist")
    # Website sign-ups have no phone or location; the old table can't hold them.
    op.execute("DELETE FROM launch_waitlist WHERE phone IS NULL OR lat IS NULL OR lng IS NULL")
    op.execute("""DELETE FROM launch_waitlist a USING launch_waitlist b
                  WHERE a.phone = b.phone AND a.created_at < b.created_at""")
    for col in ("consent_at", "source", "locale", "country", "city_text", "city_code", "email"):
        op.drop_column("launch_waitlist", col)
    op.alter_column("launch_waitlist", "lng", existing_type=sa.Float(), nullable=False)
    op.alter_column("launch_waitlist", "lat", existing_type=sa.Float(), nullable=False)
    op.alter_column("launch_waitlist", "phone", existing_type=sa.String(20), nullable=False)
    op.create_unique_constraint("uq_launch_waitlist_phone", "launch_waitlist", ["phone"])
