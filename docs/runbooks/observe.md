# Monitoring and alerts (local, zero spend)

P23 asked for Sentry, CloudWatch and an on-call paging tool. We don't pay for any
of them yet, so the same jobs run locally with open-source tools. `make observe`
starts them on top of `make dev`.

| Job | Tool | Where |
|---|---|---|
| Traces | OpenTelemetry SDK in core_api, realtime and worker → OTel collector → **Tempo** | Grafana → Explore → Tempo |
| Metrics | Prometheus `/metrics` on every service (HTTP) + the **pilot KPIs** from core_api | Grafana → *Pilot KPIs*, *Service health* |
| Logs | JSON logs (stdout) → Promtail → **Loki**, each line with its `trace_id` | Grafana → Explore → Loki (click a trace id to open the trace) |
| Alerts | Prometheus rules → **Alertmanager** → core_api webhook | The admin console (Operations, red "Alerts" box), the logs (`alert_firing` / `alert_resolved`), Alertmanager :9093 |
| Errors | `shared/observability.report_error()` logs every unexpected error. A **Sentry adapter** is in place but switched off | Logs, plus the *ErrorSpike* alert |

## Start it

```sh
make observe            # make dev + otel-collector, tempo, prometheus, alertmanager, loki, promtail, grafana
```

- Grafana: http://localhost:3300 (anonymous viewers can look; `admin`/`admin` to edit). Home is *Pilot KPIs*; pick the city at the top.
- Prometheus: http://localhost:9090/alerts
- Alertmanager: http://localhost:9093

With `make dev` alone, tracing is off and logs stay as readable console output.
`infra/docker/observe.compose.yaml` turns on `OTEL_EXPORTER_OTLP_ENDPOINT`,
`LOG_FORMAT=json` and `ALERT_WEBHOOK_TOKEN` for the three services.

## The pilot KPIs

These are per city and refresh every 30 s (`core_api/modules/orders/service/kpi.py`). They use the same
function as the admin overview, so the two always agree.

| Metric | Meaning |
|---|---|
| `bhojango_orders_live` | Orders on their way now |
| `bhojango_orders_today`, `bhojango_gmv_today` | Today's orders and their value (the city's local day, its own currency) |
| `bhojango_median_delivery_minutes` | Median delivery time of today's completed orders; empty ("—") under 5 |
| `bhojango_on_time_percent` | Delivered within 5 minutes of the promised time. Orders still out and already late count against it |
| `bhojango_completed_percent`, `bhojango_refund_percent` | Delivered (not cancelled), and delivered with a refund |
| `bhojango_orders_waiting_for_rider`, `…_5m` | Ready orders with no rider, and those waiting more than 5 minutes |
| `bhojango_orders_late` | More than 5 minutes past the promised time |
| `bhojango_payment_failures_15m` | Payments that failed in the last 15 minutes |
| `bhojango_payment_attempts_15m` | Payments that finished (succeeded or failed) in the last 15 minutes |

## The alerts (`infra/observe/prometheus/alerts.yml`)

| Alert | Fires when | What to do |
|---|---|---|
| **OrdersWithoutRider** | An order has been ready with no rider for more than 5 minutes (held 1 min) | Operations → Dispatch map: give it to a free rider |
| **PaymentFailures** | 3 or more failed payments in a city within 15 minutes, and at least 30% of the payments there (ordinary card declines at a rush don't fire it) | Check the provider's status page and the payments logs |
| **ErrorSpike** | More than 5% of a service's requests return 5xx for 2 minutes | Grafana → *Service health* → logs panel → open the trace |
| KpisNotUpdating | The KPI loop hasn't run for 5 minutes | Look for `kpi_refresh_failed` in core_api's logs |

Alertmanager posts to `POST /api/v1/ops/alerts/webhook` with a bearer token
(`ALERT_WEBHOOK_TOKEN`; empty means refused). core_api keeps one row per alert
(its fingerprint) and logs it. Admins see firing alerts for their own cities.
Platform-wide alerts (error spikes) show only to admins who can see everywhere.

### Drill (done 2026-11-12)

1. Make a ready order with no rider and backdate `actual_ready_at` by 6 minutes.
2. About 2 minutes later, *OrdersWithoutRider* was firing in Alertmanager.
3. It showed in the admin console for Hyderabad city ops (`docs/screenshots/observe/01-admin-alert.png`).
4. It was logged as `alert_firing` (visible in Loki).
5. Cancelling the order resolves it.

## Turning on paid tools later

- **Sentry**: add `sentry-sdk` to `backend/pyproject.toml` and set `SENTRY_DSN`. `shared/observability.py` then
  initialises it, and `report_error()` sends exceptions to it.
- **A paging tool** (PagerDuty, Opsgenie): add a receiver next to `bhojango-console` in
  `infra/observe/alertmanager/alertmanager.yml`. The console and log deliveries stay.
- **Hosted traces and metrics**: point `OTEL_EXPORTER_OTLP_ENDPOINT` at the vendor's OTLP endpoint (or chain it from the
  collector). Nothing in the services changes.
