# Logging (managed by mmk-crew; refreshed on every setup)

Logs are part of the feature. Design them in the first PR so they can later ship to Grafana (Loki) or our own infra
without code changes.

## Never (check these before every production release)

- **Never release to production without logs.** A new feature, endpoint, worker, cron or external call that does not
  log its start, result and failures does not ship. No log, no release.
- Never log a failure without its reason. `result=failed` or `level=error` without `error_kind` and `error` is a bug.
- Never log secrets, tokens, cookies, API keys, full emails, OAuth codes, presigned URLs or transcript/body text.
- Never log with printf or to files. No ad-hoc formats.
- Never rename a field per service. The same thing has the same name everywhere.
- Never merge on the success sample alone. The PR shows a failure log sample too.

## Format

- One JSON object per line to stdout (Go `log/slog` JSON handler; Next.js server a small JSON logger).
- Every line: `ts`, `level`, `service`, `env`, `version`, `msg`, `request_id` (or `trace_id`).
- When they apply: `user_id`, `job_id`, `provider`, `duration_ms`, `status`, `result` (`ok`, `failed`, `skipped`).
- Failure lines also: `error_kind` (short fixed code: `auth`, `decrypt`, `upstream_4xx`, `upstream_5xx`, `timeout`,
  `rate_limited`, `bad_input`, `not_found`, `internal`) and `error` (one line, secrets stripped).
- Ids and counts instead of content.

## Levels

- `error`: needs a person. `warn`: degraded but handled (retry, fallback, skip). `info`: one line per request and per
  job step. `debug`: off in production.

## Request id

- One id from the edge to the end: web server → API (`X-Request-Id`) → queue / Step Functions input → workers. A
  request can be followed across services by that one id.

## Tests and review

- Each failure path has a unit test asserting `error_kind` and `error` are present.
- A test asserts secrets never appear (feed a fake token, grep the captured log).
- The PR body has a log sample: one success line and one failure line per new path.
- The release checklist has "logs present for every new path" (see RELEASE.md).

## Shipping

- A deploy concern, not code: CloudWatch Logs subscription, OTel collector or Grafana Alloy to Grafana Cloud / Loki or
  our own store. Write the chosen sink and retention in the project docs. Keep it free-tier until the owner says
  otherwise.
