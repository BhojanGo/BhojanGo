"""Who operates BhojanGo in each country (R15): the legal entity's name in Markets settings.

Srini's decision: the US is operated by DeepTrics LLC, India by DeepTrics Software Solutions
Pvt Ltd. Only the name is set, and only where a country has no legal entity yet; the address,
support contacts, CIN, GSTIN and grievance officer are filled in admin (never invented).

Revision ID: 0035_country_legal_entity
Revises: 0034_payout_onboarding
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0035_country_legal_entity"
down_revision = "0034_payout_onboarding"
branch_labels = None
depends_on = None

ENTITIES = {"US": "DeepTrics LLC", "IN": "DeepTrics Software Solutions Pvt Ltd"}


def upgrade() -> None:
    for code, name in ENTITIES.items():
        op.execute(sa.text(
            "UPDATE countries SET settings = settings || jsonb_build_object('legal', CAST(:legal AS jsonb)) "
            "WHERE code = :code AND NOT (settings ? 'legal')").bindparams(legal=json.dumps({"name": name}), code=code))


def downgrade() -> None:
    pass  # the entity is data an admin may have edited since: leave it
