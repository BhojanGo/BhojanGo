#!/bin/sh
# core_api's server (R22): uvicorn with one process per CPU the container may use, at most
# WEB_CONCURRENCY_MAX (default 2). WEB_CONCURRENCY, when set, is the count as is.
#
# The CPU count is the container's limit (cgroup v2 cpu.max, else v1 cfs quota), not the
# host's: on Railway a container sees the whole machine's cores but may use only its share.
# Each process has its own database pool (DB_POOL_SIZE + DB_MAX_OVERFLOW connections at
# most), so replicas x processes x pool must fit Postgres' max_connections:
# docs/launch/production-config.md ("core-api processes and the database").
set -e

limit_cpus() {
  if [ -r /sys/fs/cgroup/cpu.max ]; then
    read -r quota period < /sys/fs/cgroup/cpu.max
    if [ "$quota" != "max" ] && [ "${period:-0}" -gt 0 ]; then
      echo $(( (quota + period - 1) / period )); return
    fi
  elif [ -r /sys/fs/cgroup/cpu/cpu.cfs_quota_us ]; then
    quota=$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us); period=$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us)
    if [ "$quota" -gt 0 ] && [ "$period" -gt 0 ]; then
      echo $(( (quota + period - 1) / period )); return
    fi
  fi
  nproc 2>/dev/null || echo 1
}

if [ -n "$WEB_CONCURRENCY" ]; then
  n=$WEB_CONCURRENCY
else
  n=$(limit_cpus)
  max=${WEB_CONCURRENCY_MAX:-2}
  [ "$n" -gt "$max" ] && n=$max
fi
[ "$n" -ge 1 ] 2>/dev/null || n=1
echo "core_api: $n uvicorn process(es); database pool ${DB_POOL_SIZE:-10} + ${DB_MAX_OVERFLOW:-20} each"

# Keep idle connections 130 s (uvicorn's default is 5 s): longer than the load balancer's
# idle timeout (our ALB: 120 s), so it never reuses a connection we just closed (pilot soak).
exec uvicorn core_api.main:app --host 0.0.0.0 --port "${PORT:-8001}" --timeout-keep-alive 130 --workers "$n"
