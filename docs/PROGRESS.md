# Progress

One line per merge: prompt (docs/BhojanGo_GoLive_Tracker.docx), what works, how it was tested.
Merge gate: `make ci` green locally. Zero spend: no AWS, no paid services; every provider runs locally.

| Date | Prompt / PR | What works | How it was tested |
| --- | --- | --- | --- |
| 2026-11-11 | P4 CI/CD and staging (#13) | Terraform trimmed to ADR-011 with envs/staging + envs/prod; deploy workflows skip until AWS is connected; `make ci` runs every CI check in Docker | `make ci` green (pytest 40/14/6, JS lint/typecheck/test, migrations up/down/up + `alembic check` + seed twice + integration, 3 images, terraform validate). Nothing applied to AWS |
| 2026-11-11 | Local providers (#14) | Fake payments with signed webhooks (auto-complete, decline test card, refunds), OTP/SMS and push in the worker log, fixed OTP 123456 for seed phones, email in Mailpit, ETA = straight line × 1.3, LocalStack queues/topics/buckets created on start | `make ci` green; `make dev` stack: OTP send/verify, register → welcome mail in Mailpit, fake UPI payment → webhook → succeeded → SNS → SQS → worker push log, declined card → failed, partial refund, S3 buckets (12/12 checks) |
| 2026-11-12 | P5 Sign-in and admin roles (#15) | RS256 tokens + JWKS (realtime/worker verify via JWKS), 15-min access tokens, rotating refresh tokens with reuse detection, phone OTP sign-in/sign-up (Twilio US, MSG91 India with DLT templates; log locally), Apple/Google ID tokens verified against provider keys (fixes unverified Apple tokens), account deletion, 6 admin roles scoped to country/state/city with grant/revoke API, seed admins per role | `make ci` green (165 core_api tests incl. 44-row role×scope matrix and API scope tests); `make dev` E2E 23/23: JWKS, realtime+worker accept tokens, phone sign-in seed (123456) and new number (code from worker log), refresh reuse revokes session, ops.hyd/cm.in/viewer scopes, delete account, token survives core-api restart |
