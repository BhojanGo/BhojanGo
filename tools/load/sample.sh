#!/bin/sh
# Every 5 s until killed (R21 load test, .github/workflows/load-test.yml): one CSV row per
# measurement (time,metric,value). Like tools/soak/sample.sh, more often:
#   - memory (MiB) and CPU (% of one core) per container, the k6 container included
#   - the runner as a whole: CPU busy % (all cores) and memory used (MiB)
#   - Postgres connections (all client backends, active ones) and its max_connections
#   - Redis clients and memory; established TCP connections into realtime and core-api
#   sample.sh <compose project> <out.csv>
P="$1"; OUT="$2"
echo "time,metric,value" > "$OUT"
conns() {  # <container> <port>: established connections to a local port, from /proc
  hex=$(printf '%04X' "$2")
  docker exec "$1" sh -c "cat /proc/net/tcp /proc/net/tcp6 2>/dev/null" \
    | awk -v p=":$hex" '$2 ~ p"$" && $4 == "01" {n++} END {print n+0}'
}
cpu_snap() { awk '/^cpu / {idle=$5+$6; t=0; for (i=2; i<=NF; i++) t+=$i; print idle, t}' /proc/stat; }
max=$(docker compose -p "$P" exec -T postgres psql -U bhojango -d bhojango -qAt -c "SHOW max_connections" 2>/dev/null)
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ),pg_max_connections,$max" >> "$OUT"
prev=$(cpu_snap)
while :; do
  t=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  docker stats --no-stream --format '{{.Name}},{{.MemUsage}},{{.CPUPerc}}' 2>/dev/null \
    | while IFS=, read -r name mem cpu; do
        svc=$(echo "$name" | sed -E "s/^$P-//; s/-[0-9]+$//")
        used=$(echo "$mem" | awk '{print $1}')
        mib=$(echo "$used" | awk '/GiB/ {sub("GiB",""); print $1*1024; next} /MiB/ {sub("MiB",""); print $1; next} /KiB/ {sub("KiB",""); print $1/1024; next} {print 0}')
        echo "$t,mem_mib.$svc,$mib"
        echo "$t,cpu_pct.$svc,${cpu%\%}"
      done >> "$OUT"
  cur=$(cpu_snap)
  echo "$prev $cur" | awk -v t="$t" '{di=$3-$1; dt=$4-$2; if (dt > 0) printf "%s,host_cpu_busy_pct,%.1f\n", t, 100*(1-di/dt)}' >> "$OUT"
  prev=$cur
  awk -v t="$t" '/^MemTotal:/ {tot=$2} /^MemAvailable:/ {av=$2} END {printf "%s,host_mem_used_mib,%.0f\n", t, (tot-av)/1024}' /proc/meminfo >> "$OUT"
  pg=$(docker compose -p "$P" exec -T postgres psql -U bhojango -d bhojango -qAt -c \
       "SELECT count(*) FILTER (WHERE backend_type = 'client backend'), count(*) FILTER (WHERE state = 'active' AND backend_type = 'client backend') FROM pg_stat_activity" 2>/dev/null)
  echo "$t,pg_connections,$(echo "$pg" | cut -d'|' -f1)" >> "$OUT"
  echo "$t,pg_active,$(echo "$pg" | cut -d'|' -f2)" >> "$OUT"
  info=$(docker compose -p "$P" exec -T redis redis-cli INFO 2>/dev/null | tr -d '\r')
  echo "$t,redis_clients,$(echo "$info" | awk -F: '/^connected_clients:/ {print $2}')" >> "$OUT"
  echo "$t,redis_used_mib,$(echo "$info" | awk -F: '/^used_memory:/ {printf "%.1f", $2/1048576}')" >> "$OUT"
  echo "$t,tcp_realtime,$(conns "$P-realtime-1" 8004)" >> "$OUT"
  echo "$t,tcp_core_api,$(conns "$P-core-api-1" 8001)" >> "$OUT"
  sleep 5
done
