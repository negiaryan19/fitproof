# API

All endpoints are under `/api`. The OpenAPI document is generated at `/api/openapi.json`.

## `POST /api/runs`

Creates a run and schedules the bounded investigation.

```json
{
  "device_model": "Lenovo ThinkPad T480",
  "installed_modules_gb": [8],
  "free_slots": 1,
  "upgrade_action": "add_module",
  "desired_capacity_gb": 16,
  "country": "IN",
  "part_number": "KCP432SD8/16",
  "mode": "live"
}
```

`mode` can be `live` or `replay`; it defaults to `live`. A live request returns `503` when provider configuration is incomplete. A replay request is available when `ENABLE_REPLAY=true`.

## `GET /api/runs/{run_id}`

Returns the public run state. Source text and credentials never leave the backend. It includes events, candidate offers, validated facts, checks, errors and source metadata.

## `GET /api/runs/{run_id}/events`

SSE stream of backend-generated stages. A client can reconnect with `Last-Event-ID` or the `after` query parameter. The stream ends with a `done` event.

## `POST /api/runs/{run_id}/clarifications`

Rechecks stored evidence with a corrected configuration, for example `{"installed_modules_gb": null, "free_slots": null}`. The current configuration remains user-provided and is not treated as manufacturer evidence.

## `POST /api/runs/{run_id}/offers`

Adds a user-entered exact manufacturer part number, subject to the five-candidate limit.

## `GET /api/runs/{run_id}/report`

Returns an evidence-backed Markdown report with check explanations, excerpts, publisher links and retrieval timestamps.
