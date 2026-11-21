"""Boise is live, and Basque Corner Kitchen has a photo (R27). Data only: nothing is
added, dropped or renamed.

R26: admin Markets showed Boise as "beta" while the website listed it live; the seed now
makes it live, and this does the same on databases seeded before (QA). Admin Markets
now also shows how the website lists each city, from the same rules
(markets/service/website.py).

Basque Corner Kitchen (Boise's seed kitchen, slug basque-corner-kitchen-downtown) had
no photo: no dish of its menu was in the photo library. The library now has
seafood-paella (docs/design/photos/LICENSES.md), so its Seafood Paella gets that photo
and the kitchen its cover, as the seed now does. Rows an admin or partner has changed
(a photo already set) are left alone. Cache versions are bumped by the tables' triggers
(0040), so the website sees the change on the next request.

Revision ID: 0043_boise_live_basque_photo
Revises: 0042_viewer_india_only
"""
from alembic import op

revision = "0043_boise_live_basque_photo"
down_revision = "0042_viewer_india_only"
branch_labels = None
depends_on = None

KITCHEN = "basque-corner-kitchen-downtown"


def upgrade() -> None:
    op.execute("UPDATE cities SET status = 'live', updated_at = now() WHERE code = 'US-ID-BOI' AND status = 'beta'")
    op.execute(
        "UPDATE restaurants SET cover_url = '/food/seafood-paella-1600.webp', logo_url = '/food/seafood-paella-400.webp', "
        f"updated_at = now() WHERE slug = '{KITCHEN}' AND (cover_url IS NULL OR cover_url = '')"
    )
    op.execute(
        "UPDATE menu_items SET image_url = '/food/seafood-paella-800.webp', updated_at = now() "
        f"WHERE restaurant_id IN (SELECT id FROM restaurants WHERE slug = '{KITCHEN}') "
        "AND name = 'Seafood Paella' AND (image_url IS NULL OR image_url = '')"
    )


def downgrade() -> None:
    pass  # a data fix: the older seed's beta status and the missing photo aren't worth restoring
