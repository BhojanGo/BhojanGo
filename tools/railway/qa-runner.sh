#!/bin/sh
# Drive the temporary qa-runner service in the Railway QA environment.
# Needs the Railway CLI with a QA project token in RAILWAY_TOKEN.
#   tools/railway/qa-runner.sh create        # once: the service and its variables (references only)
#   tools/railway/qa-runner.sh deploy        # upload this checkout's backend + tools and build it
#   tools/railway/qa-runner.sh job <name>    # run one job (see tools/railway/qa-job.sh), print its log
#   tools/railway/qa-runner.sh delete        # remove the service when testing is done
# Every value is a Railway reference (${{service.VAR}}): no secret passes through here.
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SVC=qa-runner
RW="${RAILWAY_BIN:-railway}"

# Wait for the current runner deployment to print the job's result line, then print its log.
wait_for_job() {
  sleep 20
  end=$(( $(date +%s) + ${QA_JOB_TIMEOUT:-1500} ))
  while :; do
    out="$($RW logs --service "$SVC" --deployment --lines 4000 2>/dev/null || true)"
    if echo "$out" | grep -q "qa-job: $1 exit="; then
      echo "$out" | sed -n "/qa-job: $1 (/,/qa-job: $1 exit=/p"
      return 0
    fi
    [ "$(date +%s)" -ge "$end" ] && { echo "qa-job $1: no result within the timeout"; echo "$out" | tail -40; return 1; }
    sleep 20
  done
}

case "${1:?usage: qa-runner.sh create|deploy|run <job>|job <job>|delete}" in
  create)
    $RW add --service "$SVC" --json </dev/null >/dev/null 2>&1 || true  # may already exist
    PG='${{postgres.POSTGRES_PASSWORD}}@postgres.railway.internal:5432'
    $RW variable set --service "$SVC" --skip-deploys \
      "DATABASE_URL=postgresql+asyncpg://bhojango:$PG/bhojango" \
      "IT_DATABASE_URL=postgresql+asyncpg://bhojango:$PG/bhojango_it" \
      'REDIS_URL=${{redis.REDIS_URL}}/0' 'IT_REDIS_URL=${{redis.REDIS_URL}}/9' \
      'EVENT_BUS=redis' 'EVENT_BUS_REDIS_URL=${{redis.REDIS_URL}}/5' \
      'APP_ENV=qa' 'PAYMENT_PROVIDER=fake' 'PAYOUT_PROVIDER=fake' 'SMS_PROVIDER=log' 'PUSH_PROVIDER=log' 'EMAIL_PROVIDER=log' \
      'UPLOADS_BUCKET=${{core-api.UPLOADS_BUCKET}}' 'AWS_ENDPOINT_URL=${{core-api.AWS_ENDPOINT_URL}}' \
      'AWS_REGION=${{core-api.AWS_REGION}}' 'AWS_ACCESS_KEY_ID=${{core-api.AWS_ACCESS_KEY_ID}}' \
      'AWS_SECRET_ACCESS_KEY=${{core-api.AWS_SECRET_ACCESS_KEY}}' 'S3_ADDRESSING_STYLE=${{core-api.S3_ADDRESSING_STYLE}}' \
      'E2E_CORE_API=https://${{core-api.RAILWAY_PUBLIC_DOMAIN}}' 'E2E_REALTIME=https://${{realtime.RAILWAY_PUBLIC_DOMAIN}}' \
      'E2E_WORKER=http://worker.railway.internal:8006' 'JWT_PRIVATE_KEY=${{core-api.JWT_PRIVATE_KEY}}' 'QA_JOB=none' >/dev/null
    # One job per deploy, then exit: no restarts, nothing running between jobs.
    $RW environment edit --service-config "$SVC" deploy.restartPolicyType NEVER --json >/dev/null
    echo "created $SVC" ;;
  deploy)
    STAGE="$(mktemp -d)"
    trap 'rm -rf "$STAGE"' EXIT
    cd "$ROOT"
    git ls-files -z --cached --others --exclude-standard -- backend tools packages/api-client/openapi \
        infra/docker/db/init.sql infra/docker/ci-migrations.sh \
      | xargs -0 -I{} sh -c '[ -f "$1" ] && mkdir -p "$2/$(dirname "$1")" && cp "$1" "$2/$1" || true' _ {} "$STAGE"
    cp infra/railway/qa-runner.Dockerfile "$STAGE/Dockerfile"
    find "$STAGE" -name "*.sh" -exec sed -i "s/\r$//" {} +   # a Windows checkout may have CRLF
    msg="qa-runner from $(git rev-parse --short HEAD)"
    cd "$STAGE" && RAILWAY_NO_CD=1 $RW up --service "$SVC" --detach -m "$msg" ;;  # up takes the current directory
  job)  # run a job on the deployed runner (setting QA_JOB redeploys it)
    JOB="${2:?job name}#$(date +%s)"
    $RW variable set --service "$SVC" "QA_JOB=$JOB" >/dev/null
    wait_for_job "$JOB" ;;
  run)  # upload this checkout and run a job on it
    JOB="${2:?job name}#$(date +%s)"
    $RW variable set --service "$SVC" "QA_JOB=$JOB" --skip-deploys >/dev/null
    sh "$0" deploy
    wait_for_job "$JOB" ;;
  delete)
    $RW service delete --service "$SVC" --yes ;;
  *) echo "unknown command" >&2; exit 2 ;;
esac
