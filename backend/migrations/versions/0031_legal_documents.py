"""Legal documents per country, versioned, and acceptance records (R8 F10).

legal_documents: Terms, Privacy (and later partner terms) per country and
language; drafts have no version, publishing gives the next one and supersedes
the previous. legal_acceptances: which published version a person accepted, when,
from where (web or app). New tables only; the seed adds the India and US drafts.

Revision ID: 0031_legal_documents
Revises: 0028_user_dispatch_pool
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0031_legal_documents"
down_revision = "0028_user_dispatch_pool"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legal_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("key_points", postgresql.JSONB(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("summary_of_changes", sa.String(500), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("published_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("kind", "country", "language", "version", name="uq_legal_documents_version"),
    )
    op.create_index("ix_legal_documents_lookup", "legal_documents", ["kind", "country", "language", "status"])
    op.create_table(
        "legal_acceptances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("legal_documents.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(160), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "document_id", name="uq_legal_acceptances_user_document"),
    )
    op.create_index("ix_legal_acceptances_user_kind", "legal_acceptances", ["user_id", "kind"])


def downgrade() -> None:
    op.drop_index("ix_legal_acceptances_user_kind", table_name="legal_acceptances")
    op.drop_table("legal_acceptances")
    op.drop_index("ix_legal_documents_lookup", table_name="legal_documents")
    op.drop_table("legal_documents")
