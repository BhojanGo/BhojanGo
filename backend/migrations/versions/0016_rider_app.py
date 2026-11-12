"""P18: delivery PIN and proof on orders; rider onboarding documents.

Revision ID: 0016_rider_app
Revises: 0015_launch_waitlist
Create Date: 2026-11-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0016_rider_app'
down_revision: Union[str, None] = '0015_launch_waitlist'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('delivery_pin', sa.String(length=4), nullable=True))
    op.add_column('orders', sa.Column('delivery_proof', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_table(
        'rider_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rider_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('file_key', sa.String(length=300), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['rider_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rider_id', 'kind', name='uq_rider_document_kind'),
    )
    op.create_index(op.f('ix_rider_documents_rider_id'), 'rider_documents', ['rider_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_rider_documents_rider_id'), table_name='rider_documents')
    op.drop_table('rider_documents')
    op.drop_column('orders', 'delivery_proof')
    op.drop_column('orders', 'delivery_pin')
