# Omni-CIO V10 — WP19 Watchtower / Incident UI Contract

## Status

WP19 extends the accepted local/private V10 Web App with a read-only incident presentation surface. It does not create or activate the future Block H Guardian/Watchtower engine.

## Canonical sources

WP19 consumes accepted `incidents`, append-only `incident_revisions`, revision-scoped `incident_evidence`/`evidence`, tenant-bound `content_blobs`, existing `journal` links, and accepted `WatchtowerAlertV1` semantics. The Watchtower reducer remains the owner of signal semantics; WP19 does not recalculate risk, credit, materiality, semantic fingerprints or requested action.

## API

Authenticated local/private endpoint: `GET /api/v10/web/watchtower-incidents`.

Tenant scope is resolved only from the existing server-side Web session. There is no tenant/user/account selector in the request. Response schema version is `1.0.0`.

Top-level fields are `generated_at`, `state = EMPTY | PARTIAL | READY`, bounded-read `truncated`, aggregate counts and `incidents[]`.

Each incident row exposes canonical incident identity, durable lifecycle/current state, verified Watchtower severity/subject/message/action/time when available, explicit risk-impact presentation, dedup/reopen state, lifecycle timeline, safe evidence metadata and already-existing Decision/Plan journal links.

## Verified Watchtower metadata

Evidence payload bytes never leave the backend. A content blob may project alert metadata only after JSON decoding and full `WatchtowerAlertV1` validation, including canonical alert identity and hard-disabled execution/trading fields. Invalid/missing content stays explicit and is not inferred.

Exactly one semantic fingerprint yields `VERIFIED`. No verified fingerprint yields `MISSING`. Multiple verified fingerprints yield `CONFLICT`; WP19 does not silently merge them.

A reopened incident is one whose durable revision history contains `closed` followed by a later `open` revision.

## UI filters

Presentation-only filters:

- all;
- active — current state is not `closed`;
- resolved — current state is `closed`;
- critical — verified severity is `error`.

WP19 provides no acknowledge/close/reopen mutation control.

## Evidence boundary

The browser may receive canonical evidence ID, source kind, publication/retrieval/local-receipt timestamps, SHA-256 content identity, safe instrument display label and booleans describing content/Watchtower validation state.

The browser never receives raw content blobs, broker credentials, secret references, provider account IDs/fingerprints, private portfolio payloads, scheduler secrets or broker-write surface.

## Failure semantics

- unauthenticated request → 401;
- no incidents → `EMPTY`;
- missing alert metadata or bounded truncation → `PARTIAL`;
- conflicting fingerprints → explicit `CONFLICT`/`PARTIAL`;
- database/API failure → request failure and explicit unavailable UI, never empty-success substitution.

## Safety invariants

`app:app`, local/private ingress, server-side session/tenant scope, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, no broker write authority, public multi-user activation locked and protected V9 rollback remain unchanged.
