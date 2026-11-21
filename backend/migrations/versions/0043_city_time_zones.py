"""Every city has its own time zone; each country a payout time zone (R27).

R26 found the United States set to America/New_York although its only cities are in
Idaho. A country's zone is now only the default for a new city; times are shown on the
city's clock (kitchen hours, admin, receipts), and finance counts its weeks in the
country's payout zone.

Schema (columns only; nothing is dropped or renamed):
  countries.payout_timezone  the zone payout weeks are counted in (NULL = countries.timezone)

Data (QA and production):
  cities.timezone            filled where empty: the city's state's zone, else its country's
                             (Boise and Nampa -> America/Boise, Hyderabad etc. -> Asia/Kolkata)
  countries.payout_timezone  US -> America/Boise (its cities are in Idaho, for now);
                             IN -> Asia/Kolkata; any other country -> its own timezone

Revision ID: 0043_city_time_zones
Revises: 0042_viewer_india_only
"""
import sqlalchemy as sa
from alembic import op

revision = "0043_city_time_zones"
down_revision = "0042_viewer_india_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("countries", sa.Column("payout_timezone", sa.String(50), nullable=True))
    # Southern Idaho is on Mountain time whatever its state row says.
    op.execute("UPDATE cities SET timezone = 'America/Boise' WHERE code IN ('US-ID-BOI', 'US-ID-NMP') "
               "AND (timezone IS NULL OR timezone = '' OR timezone = 'America/New_York')")
    op.execute("""
        UPDATE cities c SET timezone = COALESCE(r.timezone, k.timezone)
        FROM regions r, countries k
        WHERE r.id = c.region_id AND k.id = c.country_id AND (c.timezone IS NULL OR c.timezone = '')
    """)
    op.execute("UPDATE countries SET payout_timezone = 'America/Boise' WHERE code = 'US'")
    op.execute("UPDATE countries SET payout_timezone = 'Asia/Kolkata' WHERE code = 'IN'")
    op.execute("UPDATE countries SET payout_timezone = timezone WHERE payout_timezone IS NULL")
    # (cached zones follow: the cache_versions triggers bump "markets" on these updates)


def downgrade() -> None:
    op.drop_column("countries", "payout_timezone")
