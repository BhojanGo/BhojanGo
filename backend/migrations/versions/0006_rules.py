"""P7 rules: rules (versioned, scoped), rule_approvals (maker-checker), audit_log.

Revision ID: 0006_rules
Revises: 0005_markets
Create Date: 2026-11-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0006_rules'
down_revision: Union[str, None] = '0005_markets'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('audit_log',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('actor_id', sa.UUID(), nullable=True),
    sa.Column('action', sa.String(length=40), nullable=False),
    sa.Column('entity_type', sa.String(length=40), nullable=False),
    sa.Column('entity_id', sa.String(length=64), nullable=False),
    sa.Column('scope', sa.String(length=20), nullable=False),
    sa.Column('before', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('after', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_log_actor_id'), 'audit_log', ['actor_id'], unique=False)
    op.create_index(op.f('ix_audit_log_at'), 'audit_log', ['at'], unique=False)
    op.create_index('ix_audit_log_entity', 'audit_log', ['entity_type', 'entity_id'], unique=False)
    op.create_index(op.f('ix_audit_log_scope'), 'audit_log', ['scope'], unique=False)
    op.create_table('rules',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('rule_key', sa.UUID(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('family', sa.String(length=20), nullable=False),
    sa.Column('template', sa.String(length=30), nullable=False),
    sa.Column('key', sa.String(length=40), nullable=True),
    sa.Column('slot', sa.String(length=100), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=True),
    sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('scope_level', sa.String(length=12), nullable=False),
    sa.Column('scope_id', sa.String(length=64), nullable=False),
    sa.Column('market_scope', sa.String(length=20), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('locked', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('effective_from', sa.DateTime(timezone=True), nullable=False),
    sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('rule_key', 'version', name='uq_rules_key_version')
    )
    op.create_index('ix_rules_lookup', 'rules', ['status', 'scope_level', 'scope_id'], unique=False)
    op.create_index(op.f('ix_rules_market_scope'), 'rules', ['market_scope'], unique=False)
    op.create_index(op.f('ix_rules_rule_key'), 'rules', ['rule_key'], unique=False)
    op.create_index(op.f('ix_rules_slot'), 'rules', ['slot'], unique=False)
    op.create_table('rule_approvals',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('rule_id', sa.UUID(), nullable=False),
    sa.Column('requested_by', sa.UUID(), nullable=False),
    sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('decision', sa.String(length=10), nullable=True),
    sa.Column('decided_by', sa.UUID(), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['rule_id'], ['rules.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rule_approvals_rule_id'), 'rule_approvals', ['rule_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_rule_approvals_rule_id'), table_name='rule_approvals')
    op.drop_table('rule_approvals')
    op.drop_index(op.f('ix_rules_slot'), table_name='rules')
    op.drop_index(op.f('ix_rules_rule_key'), table_name='rules')
    op.drop_index(op.f('ix_rules_market_scope'), table_name='rules')
    op.drop_index('ix_rules_lookup', table_name='rules')
    op.drop_table('rules')
    op.drop_index(op.f('ix_audit_log_scope'), table_name='audit_log')
    op.drop_index('ix_audit_log_entity', table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_at'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_actor_id'), table_name='audit_log')
    op.drop_table('audit_log')
