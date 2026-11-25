# Monitoring: what to paste, and how to check it

Everything is wired (round 39). Production needs only **two kinds of values pasted into Railway**: the
Sentry DSNs and one paging webhook URL. Nothing else changes, and nothing is sent anywhere until they are set.

## The values

| Variable | Railway service(s) | Where it comes from | What it turns on |
|---|---|---|---|
| `SENTRY_DSN` | core-api, realtime, worker (sealed) | Sentry: the backend project > Settings > Client Keys (DSN) | Error reports from the backend (`backend/shared/observability.py`; errors only, no request bodies or personal data) |
| `NEXT_PUBLIC_SENTRY_DSN` | web, admin (sealed; a build variable) | Sentry: the web project (and the admin project, or the same one) > Client Keys | Error reports from the website and admin, browser and server (`apps/*/src/instrumentation*.ts`) |
| `EXPO_PUBLIC_SENTRY_DSN` | the EAS build profiles of the 3 apps | Sentry: one project per app, or one shared | Error reports from the apps (`apps/*/app/_layout.tsx`); set before the store builds |
| `PAGING_WEBHOOK_URL` | core-api (sealed) | The on-call tool's incoming webhook | Pages for critical alerts and chargebacks (`backend/shared/paging.py`) |

Already set by the go-live steps (not new): `ALERT_WEBHOOK_TOKEN` (Alertmanager to core-api; `openssl rand -hex 32`).

`tools/railway/prod_config_check.py` lists `PAGING_WEBHOOK_URL` and the DSNs as "set by hand from Srini's accounts".

## The paging webhook

One JSON POST per page, readable as is by the common receivers:

```json
{"text": "[CRITICAL] Orders without a delivery partner (production)\n3 orders in Boise ...",
 "content": "... the same, for Discord ...", "title": "[CRITICAL] ...", "message": "...", "priority": 5,
 "severity": "critical", "environment": "production", "source": "bhojango", "details": {"alert": "...", "city": "US-ID-BOI"}}
```

- **Slack** (incoming webhook) and **Mattermost / Google Chat** read `text`; **Discord** reads `content`.
- **ntfy** (a topic URL, free, a phone app that rings) reads `title`, `message` and `priority`.
- **PagerDuty / Opsgenie**: use their generic "incoming webhook" or email-to-page integration URL; for PagerDuty's
  Events API v2 put a tiny relay in front (its body needs a routing key).

What pages:

- Alertmanager alerts with `severity: critical` when they **start** firing (`infra/observe/prometheus` rules:
  payment failures, orders without a delivery partner, error spikes...). A repeat of a firing alert doesn't page again.
- Alerts the code raises as pages: a **chargeback opened** (R39) and the **BhojanGo offer budget used up** (R37,
  shown on the Operations page).
- Admin **Settings > Monitoring > "Send test alert"** (super admins).

Every alert also shows on the admin Operations page and is a log line, with or without paging. A page that fails
(the receiver is down, the URL is wrong) is logged as `page_failed` and never breaks what raised it. The URL itself
is never logged.

## After pasting: the check

1. Redeploy core-api (and the web and admin builds for `NEXT_PUBLIC_SENTRY_DSN`).
2. Admin > Settings > Monitoring > **Send test alert**. The result reads, for each channel, *sent*, *off (not set)*
   or *failed*:
   - Operations page: always *sent* (a "TestAlert" row, resolved at once).
   - Paging webhook: *sent* means the receiver answered 2xx. Check that the phone rang.
   - Sentry: *sent* means the SDK accepted the event. Check that it shows in the backend project.
3. Website, admin and apps send only real errors: check them with Sentry's own "Verify installation" step for
   each project.

## Tests

- `backend/core_api/modules/support/tests/test_paging.py`: the webhook body and the off/failed paths against a real
  local HTTP server (`core_api/integration/mock_webhook.py`).
- `backend/core_api/integration/test_observe.py::test_paging_and_the_test_alert_button`: a new critical
  Alertmanager alert pages once, a repeat doesn't; "Send test alert" reaches the mock webhook; a failing receiver
  reads *failed*; only a super admin may send it.
- `backend/core_api/integration/test_r39_disputes.py`: a chargeback pages once.
