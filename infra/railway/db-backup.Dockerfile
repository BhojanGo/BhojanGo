# Hourly database backup (R22): Postgres 16's own pg_dump (the same major version as the
# server, infra/railway/postgis.Dockerfile) plus the AWS CLI for the S3-compatible bucket.
# A Railway cron service runs it every hour (.railway/railway.ts, service db-backup).
FROM postgres:16-alpine
RUN apk add --no-cache aws-cli
COPY tools/backup/hourly_dump.sh /usr/local/bin/hourly_dump.sh
USER postgres
CMD ["sh", "/usr/local/bin/hourly_dump.sh"]
