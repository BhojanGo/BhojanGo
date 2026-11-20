#!/bin/sh
# Profile core-api during the load test (R21): wait, then sample every uvicorn process in
# the core-api container with py-spy for a minute (a side container sharing its process
# namespace; nothing is installed in core-api). Writes collapsed stacks ("frame;frame N").
#   profile.sh <compose project> <out dir> [delay s] [seconds]
P="$1"; OUT="$2"; DELAY="${3:-600}"; SECS="${4:-60}"
sleep "$DELAY"
docker run --rm --pid "container:$P-core-api-1" --cap-add SYS_PTRACE -v "$OUT:/out" python:3.12-slim \
  sh -c "pip install -q py-spy==0.4.0 >/dev/null 2>&1 && py-spy record --subprocesses --pid 1 --duration $SECS --rate 50 --format raw --output /out/profile-core-api.txt --nonblocking" \
  > "$OUT/profile.log" 2>&1
echo "profile exit $?" >> "$OUT/profile.log"
