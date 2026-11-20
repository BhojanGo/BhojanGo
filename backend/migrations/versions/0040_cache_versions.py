"""Cache versions (R22): the database itself records every edit to what core_api caches.

core_api caches menus, store hours, a kitchen's market, the rules and the cities in each
process (shared/cache_versions.py). Every cached copy is keyed by the current version of
the scopes below, read from this table on each use, so an edit is seen by the very next
request, in every process, however it was made: the API, the worker, a script or psql.
The triggers run in the writing transaction, so a new version is visible exactly when the
edit commits (and never if it rolls back). Versions come from a sequence, so a rolled-back
version number is never used again.

Rows are only ever inserted (never updated), so writers never wait on each other here.
A scope's version is its highest row (the primary key's index answers that directly).
Old rows can be deleted at any time (keep each scope's highest): about one row per edit.

Scopes:
  kitchen:<restaurant id>  the kitchen, its menu (categories, items, option groups and
                           options), its hours and day overrides
  kitchen:*                a kitchen write whose kitchen can't be told (an option or link
                           whose parent is gone, a TRUNCATE): every kitchen's caches
  kitchens                 any of the above (the home screen's city facts)
  markets                  countries, regions, cities, zones
  rules                    the rules
  orders:<restaurant id>   a kitchen's orders (the kitchen tablet's board)
  orders:*                 orders whose kitchen can't be told (a TRUNCATE)
  people                   a user's name changed, or a user was deleted (names on the board)

Revision ID: 0040_cache_versions
Revises: 0039_region_short_code
"""
from alembic import op

revision = "0040_cache_versions"
down_revision = "0039_region_short_code"
branch_labels = None
depends_on = None

KITCHEN_TABLES = {  # table -> its restaurant id, from a row ("{r}" is NEW or OLD)
    "restaurants": "{r}.id",
    "menu_categories": "{r}.restaurant_id",
    "menu_items": "{r}.restaurant_id",
    "option_groups": "{r}.restaurant_id",
    "store_hours": "{r}.restaurant_id",
    "store_hour_overrides": "{r}.restaurant_id",
    "options": "(SELECT g.restaurant_id FROM option_groups g WHERE g.id = {r}.group_id)",
    "menu_item_option_groups": "(SELECT i.restaurant_id FROM menu_items i WHERE i.id = {r}.menu_item_id)",
}
GLOBAL_TABLES = {"countries": "markets", "regions": "markets", "cities": "markets", "zones": "markets", "rules": "rules"}


def upgrade() -> None:
    op.execute("CREATE SEQUENCE cache_version_seq")
    op.execute("CREATE TABLE cache_versions (scope varchar(80) NOT NULL, version bigint NOT NULL, "
               "PRIMARY KEY (scope, version))")
    op.execute("""
        CREATE FUNCTION cache_bump(s text) RETURNS void LANGUAGE sql AS $$
            INSERT INTO cache_versions (scope, version) VALUES (s, nextval('cache_version_seq'))
        $$""")
    op.execute("""
        CREATE FUNCTION cache_bump_kitchen(rid uuid) RETURNS void LANGUAGE sql AS $$
            SELECT cache_bump(CASE WHEN rid IS NULL THEN 'kitchen:*' ELSE 'kitchen:' || rid::text END)
        $$""")
    op.execute("""
        CREATE FUNCTION cache_bump_scope() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE s text;
        BEGIN
            FOREACH s IN ARRAY TG_ARGV LOOP
                PERFORM cache_bump(s);
            END LOOP;
            RETURN NULL;
        END $$""")
    for table, find in KITCHEN_TABLES.items():
        fn = f"cache_bump_{table}"
        new, old = find.format(r="NEW"), find.format(r="OLD")
        op.execute(f"""
            CREATE FUNCTION {fn}() RETURNS trigger LANGUAGE plpgsql AS $$
            DECLARE a uuid; b uuid;
            BEGIN
                IF TG_OP <> 'DELETE' THEN a := {new}; END IF;
                IF TG_OP <> 'INSERT' THEN b := {old}; END IF;
                IF TG_OP <> 'DELETE' THEN PERFORM cache_bump_kitchen(a); END IF;
                IF TG_OP = 'DELETE' OR (TG_OP = 'UPDATE' AND b IS DISTINCT FROM a) THEN
                    PERFORM cache_bump_kitchen(b);
                END IF;
                PERFORM cache_bump('kitchens');
                RETURN NULL;
            END $$""")
        op.execute(f"CREATE TRIGGER {fn} AFTER INSERT OR UPDATE OR DELETE ON {table} "
                   f"FOR EACH ROW EXECUTE FUNCTION {fn}()")
        op.execute(f"CREATE TRIGGER {fn}_truncate AFTER TRUNCATE ON {table} "
                   f"FOR EACH STATEMENT EXECUTE FUNCTION cache_bump_scope('kitchen:*', 'kitchens')")
    for table, scope in GLOBAL_TABLES.items():
        op.execute(f"CREATE TRIGGER cache_bump_{table} AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON {table} "
                   f"FOR EACH STATEMENT EXECUTE FUNCTION cache_bump_scope('{scope}')")
    # The kitchen board: a kitchen's orders, and the names shown on them.
    op.execute("""
        CREATE FUNCTION cache_bump_orders() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP <> 'DELETE' THEN PERFORM cache_bump('orders:' || NEW.restaurant_id::text); END IF;
            IF TG_OP = 'DELETE' OR (TG_OP = 'UPDATE' AND OLD.restaurant_id IS DISTINCT FROM NEW.restaurant_id) THEN
                PERFORM cache_bump('orders:' || OLD.restaurant_id::text);
            END IF;
            RETURN NULL;
        END $$""")
    op.execute("CREATE TRIGGER cache_bump_orders AFTER INSERT OR UPDATE OR DELETE ON orders "
               "FOR EACH ROW EXECUTE FUNCTION cache_bump_orders()")
    op.execute("CREATE TRIGGER cache_bump_orders_truncate AFTER TRUNCATE ON orders "
               "FOR EACH STATEMENT EXECUTE FUNCTION cache_bump_scope('orders:*')")
    op.execute("CREATE TRIGGER cache_bump_people AFTER UPDATE OF full_name OR DELETE ON users "
               "FOR EACH STATEMENT EXECUTE FUNCTION cache_bump_scope('people')")
    op.execute("CREATE TRIGGER cache_bump_people_truncate AFTER TRUNCATE ON users "
               "FOR EACH STATEMENT EXECUTE FUNCTION cache_bump_scope('people')")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS cache_bump_people_truncate ON users")
    op.execute("DROP TRIGGER IF EXISTS cache_bump_people ON users")
    op.execute("DROP TRIGGER IF EXISTS cache_bump_orders_truncate ON orders")
    op.execute("DROP TRIGGER IF EXISTS cache_bump_orders ON orders")
    op.execute("DROP FUNCTION IF EXISTS cache_bump_orders()")
    for table in GLOBAL_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS cache_bump_{table} ON {table}")
    for table in KITCHEN_TABLES:
        fn = f"cache_bump_{table}"
        op.execute(f"DROP TRIGGER IF EXISTS {fn}_truncate ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS {fn} ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS {fn}()")
    op.execute("DROP FUNCTION IF EXISTS cache_bump_scope()")
    op.execute("DROP FUNCTION IF EXISTS cache_bump_kitchen(uuid)")
    op.execute("DROP FUNCTION IF EXISTS cache_bump(text)")
    op.execute("DROP TABLE IF EXISTS cache_versions")
    op.execute("DROP SEQUENCE IF EXISTS cache_version_seq")
