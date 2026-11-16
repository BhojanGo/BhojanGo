"""Help centre (round 8, F9): help articles managed in the admin console, their
versions, "Was this helpful?" votes; support tickets from people who are not
signed in (the Help contact form), so a ticket's requester may be empty.

Revision ID: 0030_help_centre
Revises: 0028_user_dispatch_pool
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0030_help_centre"
down_revision = "0028_user_dispatch_pool"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "help_articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("topic", sa.String(30), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("language", sa.String(5), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("summary", sa.String(300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("popular", sa.Integer(), nullable=False),
        sa.Column("related", postgresql.JSONB(), nullable=False),
        sa.Column("draft", postgresql.JSONB(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint("slug", "country", "language", name="uq_help_articles_slug_country_language"),
    )
    op.create_index("ix_help_articles_slug", "help_articles", ["slug"])
    op.create_table(
        "help_article_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("help_articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_help_article_versions_article_id", "help_article_versions", ["article_id"])
    op.create_table(
        "help_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("help_articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("voter", sa.String(64), nullable=False),
        sa.Column("helpful", sa.Boolean(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("article_id", "voter", name="uq_help_votes_article_voter"),
    )
    op.create_index("ix_help_votes_article_id", "help_votes", ["article_id"])
    # The Help contact form: a ticket from someone who is not signed in (name and email in details).
    op.alter_column("support_tickets", "requester_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM support_tickets WHERE requester_id IS NULL")
    op.alter_column("support_tickets", "requester_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.drop_index("ix_help_votes_article_id", table_name="help_votes")
    op.drop_table("help_votes")
    op.drop_index("ix_help_article_versions_article_id", table_name="help_article_versions")
    op.drop_table("help_article_versions")
    op.drop_index("ix_help_articles_slug", table_name="help_articles")
    op.drop_table("help_articles")
