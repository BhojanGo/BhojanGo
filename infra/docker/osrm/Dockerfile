# R31: road distance for local and QA, free and self-hosted: OSRM (car profile) on OpenStreetMap roads around
# the live cities (Boise, Hyderabad). No API key, no paid service. Map data (c) OpenStreetMap contributors, ODbL.
#   docker compose -f infra/docker/compose.yaml build osrm      # once; bump the snapshot below to refresh
# State extracts (Geofabrik: Idaho, a dated snapshot; openstreetmap.fr: Telangana), clipped to each city's box
# with osmium and merged. A new city: add its extract and box. When OSRM is down, the API falls back to
# straight-line x ROAD_FACTOR and logs routing_fallback (backend/shared/providers/routing.py).
FROM debian:bookworm-slim AS fetch
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl osmium-tool \
    && rm -rf /var/lib/apt/lists/*
ARG IDAHO=https://download.geofabrik.de/north-america/us/idaho/idaho-260101.osm.pbf
ARG TELANGANA=https://download.openstreetmap.fr/extracts/asia/india/telangana-latest.osm.pbf
RUN curl -fsSL -A "osrm-map-build/1.0" --retry 3 --retry-delay 20 -o /tmp/idaho.osm.pbf "$IDAHO" \
    && curl -fsSL -A "osrm-map-build/1.0" --retry 3 --retry-delay 20 -o /tmp/telangana.osm.pbf "$TELANGANA" \
    && osmium extract -b -116.45,43.45,-115.95,43.78 /tmp/idaho.osm.pbf -o /tmp/boise.osm.pbf \
    && osmium extract -b 78.25,17.25,78.62,17.60 /tmp/telangana.osm.pbf -o /tmp/hyderabad.osm.pbf \
    && osmium merge /tmp/boise.osm.pbf /tmp/hyderabad.osm.pbf -o /tmp/map.osm.pbf \
    && rm /tmp/idaho.osm.pbf /tmp/telangana.osm.pbf /tmp/boise.osm.pbf /tmp/hyderabad.osm.pbf

FROM ghcr.io/project-osrm/osrm-backend:v5.27.1 AS build
COPY --from=fetch /tmp/map.osm.pbf /data/map.osm.pbf
RUN osrm-extract -p /opt/car.lua /data/map.osm.pbf \
    && osrm-partition /data/map.osrm \
    && osrm-customize /data/map.osrm \
    && rm /data/map.osm.pbf

FROM ghcr.io/project-osrm/osrm-backend:v5.27.1
COPY --from=build /data /data
EXPOSE 5000
CMD ["osrm-routed", "--algorithm", "mld", "--max-table-size", "500", "--port", "5000", "/data/map.osrm"]
