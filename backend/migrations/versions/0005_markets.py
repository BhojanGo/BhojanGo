"""P6 markets: countries, regions (states), cities and zones (PostGIS polygons).

Revision ID: 0005_markets
Revises: 0004_identity_p5
Create Date: 2026-11-12

"""
from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0005_markets'
down_revision: Union[str, None] = '0004_identity_p5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('countries',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('code', sa.String(length=2), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('locales', postgresql.ARRAY(sa.String(length=10)), nullable=False),
    sa.Column('timezone', sa.String(length=50), nullable=False),
    sa.Column('distance_unit', sa.String(length=2), nullable=False),
    sa.Column('phone_code', sa.String(length=5), nullable=False),
    sa.Column('payment_providers', postgresql.ARRAY(sa.String(length=20)), nullable=False),
    sa.Column('tax_regime', sa.String(length=20), nullable=False),
    sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('regions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('country_id', sa.UUID(), nullable=False),
    sa.Column('code', sa.String(length=10), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('timezone', sa.String(length=50), nullable=True),
    sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['country_id'], ['countries.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_index(op.f('ix_regions_country_id'), 'regions', ['country_id'], unique=False)
    op.create_table('cities',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('country_id', sa.UUID(), nullable=False),
    sa.Column('region_id', sa.UUID(), nullable=False),
    sa.Column('code', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('timezone', sa.String(length=50), nullable=True),
    sa.Column('service_hours', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('center_lat', sa.Float(), nullable=False),
    sa.Column('center_lng', sa.Float(), nullable=False),
    sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['country_id'], ['countries.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['region_id'], ['regions.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_index(op.f('ix_cities_country_id'), 'cities', ['country_id'], unique=False)
    op.create_index(op.f('ix_cities_region_id'), 'cities', ['region_id'], unique=False)
    op.create_table('zones',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('city_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('polygon', geoalchemy2.types.Geometry(geometry_type='POLYGON', srid=4326, dimension=2, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('min_order', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('color', sa.String(length=7), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('pause_reason', sa.Text(), nullable=True),
    sa.Column('paused_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['city_id'], ['cities.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('city_id', 'name', name='uq_zones_city_name')
    )
    op.create_index(op.f('ix_zones_city_id'), 'zones', ['city_id'], unique=False)
    op.create_index('ix_zones_polygon', 'zones', ['polygon'], unique=False, postgresql_using='gist')


def downgrade() -> None:
    op.drop_index('ix_zones_polygon', table_name='zones', postgresql_using='gist')
    op.drop_index(op.f('ix_zones_city_id'), table_name='zones')
    op.drop_table('zones')
    op.drop_index(op.f('ix_cities_region_id'), table_name='cities')
    op.drop_index(op.f('ix_cities_country_id'), table_name='cities')
    op.drop_table('cities')
    op.drop_index(op.f('ix_regions_country_id'), table_name='regions')
    op.drop_table('regions')
    op.drop_table('countries')
