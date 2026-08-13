# Omni-CIO V10 — WP19 Watchtower / Incident UI Contract

## Status

WP19 extends the accepted local/private V10 Web App with a read-only incident presentation surface. It does not create or activate the future Block H Guardian/Watchtower engine.

## Canonical sources

WP19 consumes only accepted state:

- `omni_cio_v10.incidents` — immutable incident identity and `opened_at`;
- `omni_cio_v10.incident_revisions` — append-only lifecycle revisions and `revised_at`;
- `omni_cio_v10.incident_evidence` + `evidence` — revision-scoped evidence references and source/time metadata;
- `omni_cio_v10.content_blobs` — server-side content lookup by exact evidence SHA-256;
- `omni_cio_v10.journal` — already-existing Decision/Plan links;
- accepted `WatchtowerAlertV1` — deterministic alert identity, semantic fingerprint, severity, subject, effective time, safe message code and requested non-execution action.

The V9 Watchtower reducer remains the owner of signal semantics. WP19 does not recalculate risk, credit, materiality, dedup fingerprints or proposed actions.

## API

Authenticated local/private endpoint:

`GET /api/v10/web/watchtower-incidents`

The tenant is resolved only from the existing server-side Web session. There is no tenant/user/account selector in the request.

Response schema version: `1.0.0`.

Top-level fields:

- `generated_at` — UTC presentation generation time;
- `state` — `EMPTY | PARTIAL | READY`;
- `truncated` — explicit bounded-read indicator;
- `counts.total | active | resolved | critical | reopened | missing_alert_metadata`;
- `incidents[]` — bounded incident presentation rows.

Each incident row exposes:

- canonical `incident_id`;
- `opened_at`;
- current durable lifecycle state and `ACTIVE | RESOLVED` presentation classification;
- verified Watchtower severity or `unknown`;
- explicit risk-impact presentation `CRITICAL | MATERIAL | INFORMATIONAL | UNKNOWN` derived only from the accepted severity taxonomy;
- verified subject/message-code/requested-action/effective-time when canonical alert metadata is available;
- `alert_metadata_state = VERIFIED | MISSING | CONFLICT`;
- dedup status and semantic fingerprint only when exactly one verified fingerprint is present;
- `reopened=true` only when the durable lifecycle contains `closed` followed by a later `open` revision;
- complete durable timeline of revision/status/time and revision-scoped evidence IDs;
- bounded evidence metadata without raw content;
- already-existing Decision/Plan IDs linked by the accepted journal.

## Verified Watchtower metadata

Evidence payload bytes never leave the backend. WP19 may project alert metadata only when the content blob:

1. is found by exact tenant + evidence `payload_sha256`;
2. decodes as JSON;
3. fully validates as accepted `WatchtowerAlertV1`, including canonical `alert_id` validation and hard-disabled execution/trading fields.

If validation fails, the payload is ignored as alert metadata and the browser receives only an explicit missing/invalid presentation state. Raw invalid content is never returned.

If multiple valid alert payloads linked to one incident contain different semantic fingerprints, dedup state is `CONFLICT`; WP19 does not silently choose or merge the conflicting condition identity.

## Lifecycle and filters

UI filters are presentation-only:

- **Все** — all bounded incidents;
- **Активные** — current state is not `closed`;
- **Решённые** — current state is `closed`;
- **Критические** — verified severity is `error`.

A reopened incident remains active and carries `reopened=true`.

WP19 provides no acknowledge/close/reopen button. Lifecycle mutation belongs to its owning future system workflow and is outside this Web WP.

## Evidence semantics

The Web view may expose:

- canonical evidence ID;
- evidence source kind;
- publication/retrieval/local-receipt timestamps when available;
- SHA-256 content identity;
- safe instrument display label (ticker/name) only if already present in canonical instrument metadata;
- booleans indicating whether content exists and whether it validated as `WatchtowerAlertV1`.

It never exposes:

- raw content blob;
- broker token, secret reference or encryption material;
- provider account ID/fingerprint;
- private portfolio payload/holdings;
- scheduler/QStash/Upstash secrets;
- broker-write or trade surface.

## Failure semantics

- unauthenticated request: HTTP 401;
- no incidents: `EMPTY`, never fake zero incidents after a database failure;
- missing alert content/metadata: `PARTIAL` with explicit `MISSING`;
- semantic fingerprint conflict: `PARTIAL` with explicit `CONFLICT`;
- bounded read overflow: `PARTIAL` and `truncated=true`;
- API/database failure: request fails and Web shows an explicit unavailable state.

## Safety invariants

WP19 preserves:

- `app:app` protected Gateway entrypoint;
- local/private Web ingress only;
- server-side tenant/session scope;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no broker write authority;
- no public multi-user activation;
- protected V9 rollback.
