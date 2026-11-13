# Postgres for Railway, with PostGIS (markets and zones use geography types).
# Railway's own Postgres image (SSL certificates, its start-up script), plus
# the PostGIS package from the PostgreSQL apt repository the image already
# uses. Migrations create the extensions (backend/migrations/versions/0003).
# Same major versions as local: Postgres 16, PostGIS 3 (compose: postgis/postgis:16-3.x).
FROM ghcr.io/railwayapp-templates/postgres-ssl:16
RUN apt-get update \
 && apt-get install -y --no-install-recommends "postgresql-${PG_MAJOR}-postgis-3" \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/*
