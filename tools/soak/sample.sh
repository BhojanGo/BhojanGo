#!/bin/sh
# Once a minute until killed: one CSV row per measurement (time,metric,value).
#   sample.sh <compose project> <out.csv>
# Memory and CPU per container, Postgres connections, Redis clients and memory,
# and established TCP connections into realtime (WebSockets) and core_api.
P="$1"; OUT="$2"
export MSYS_NO_PATHCONV=1
echo "time,metric,value" > "$OUT"
# Established connections to a local port, from /proc (no tools needed in the image).
conns() {  # <container> <port>
  hex=$(printf '%04X' "$2")
  docker exec "$1" sh -c "cat /proc/net/tcp /proc/net/tcp6 2>/dev/null" \
    | awk -v p=":$hex" '$2 ~ p"$" && $4 == "01" {n++} END {print n+0}'
}
while :; do
  t=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  docker stats --no-stream --format '{{.Name}},{{.MemUsage}},{{.CPUPerc}}' $(docker ps -q --filter "label=com.docker.compose.project=$P") 2>/dev/null \
    | while IFS=, read -r name mem cpu; do
        svc=$(echo "$name" | sed -E "s/^$P-//; s/-[0-9]+$//")
        used=$(echo "$mem" | awk '{print $1}')
        mib=$(echo "$used" | awk '/GiB/ {sub("GiB",""); print $1*1024; next} /MiB/ {sub("MiB",""); print $1; next} /KiB/ {sub("KiB",""); print $1/1024; next} {print 0}')
        echo "$t,mem_mib.$svc,$mib"
        echo "$t,cpu_pct.$svc,${cpu%\%}"
      done >> "$OUT"
  pg=$(docker compose -p "$P" exec -T postgres psql -U bhojango -d bhojango -qAt -c \
       "SELECT count(*) FILTER (WHERE backend_type = 'client backend'), count(*) FILTER (WHERE state = 'active' AND backend_type = 'client backend') FROM pg_stat_activity" 2>/dev/null)
  echo "$t,pg_connections,$(echo "$pg" | cut -d'|' -f1)" >> "$OUT"
  echo "$t,pg_active,$(echo "$pg" | cut -d'|' -f2)" >> "$OUT"
  info=$(docker compose -p "$P" exec -T redis redis-cli INFO 2>/dev/null | tr -d '\r')
  echo "$t,redis_clients,$(echo "$info" | awk -F: '/^connected_clients:/ {print $2}')" >> "$OUT"
  echo "$t,redis_used_mib,$(echo "$info" | awk -F: '/^used_memory:/ {printf "%.1f", $2/1048576}')" >> "$OUT"
  echo "$t,redis_keys,$(echo "$info" | awk -F'[:=,]' '/^db[0-9]+:/ {n += $3} END {print n+0}')" >> "$OUT"
  echo "$t,tcp_realtime,$(conns "$P-realtime-1" 8004)" >> "$OUT"
  echo "$t,tcp_core_api,$(conns "$P-core-api-1" 8001)" >> "$OUT"
  sleep 60
done
