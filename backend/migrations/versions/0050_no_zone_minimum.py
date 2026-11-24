"""No platform-level minimum order (R36). Data only: no column is added, dropped or renamed.

  * Every zone's minimum order becomes 0 (the seeds say 0 too). A restaurant's own minimum stays, and the
    cart now shows the full bill with "Add ₹x more" until it's met (the order is refused below it).
  * Boise Bowl Co. (the demo/QA kitchen, slug boise-bowl-co-hyde-park): its own minimum $15.00, as in the seed.

Only rows that exist are touched (QA and local; an empty database is left alone). The old zone minimums aren't
kept: downgrade leaves the data as it is.

Revision ID: 0050_no_zone_minimum
Revises: 0049_idaho_tax_lines
"""
from alembic import op

revision = "0050_no_zone_minimum"
down_revision = "0049_idaho_tax_lines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE zones SET min_order = 0 WHERE min_order IS NOT NULL AND min_order <> 0")
    op.execute("UPDATE restaurants SET minimum_order_amount = 15.00 WHERE slug = 'boise-bowl-co-hyde-park'")


def downgrade() -> None:
    pass  # data only: the old minimums aren't restored
