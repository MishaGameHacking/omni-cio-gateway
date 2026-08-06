# Omni-CIO V10 — OWNER Account and T-Invest Connection Contract

**Status:** OWNER-APPROVED ARCHITECTURE / IMPLEMENTATION CONTRACT  
**Date:** 2026-08-06  
**Program authority:** `docs/master-plan/OMNI_CIO_V10_PRODUCTIZATION_AND_OWNER_ACCOUNT_AMENDMENT.md`  
**Web authority:** `docs/architecture/V10_WEB_PRODUCT_BLUEPRINT.md`

## 1. Goal

Define exactly how the V10 Personal Web account, authentication boundary and T-Invest connections must behave so later implementation does not invent credential semantics inside UI code.

V10 Personal has one active OWNER account in production. Public registration and public multi-user operation are out of scope, while storage/API boundaries remain future-isolation-ready.

## 2. Conceptual domain objects

The exact DB schema is owned by Block D, but it must represent the following responsibilities explicitly.

### OwnerIdentity

Safe metadata only:

- `user_id`;
- status (`active`, `locked`, `recovery_required`, disabled where applicable);
- created/updated timestamps;
- presentation timezone/locale;
- authentication/recovery metadata that is safe to persist;
- no broker secret value.

### OwnerSession

- session ID/hash/reference;
- OWNER identity;
- issued/last-seen/expiry times;
- auth strength / recent step-up time when relevant;
- revocation state;
- device/client metadata only when required by security policy;
- no broker secret.

### BrokerConnection

Metadata object, not secret storage:

- connection ID;
- broker = `T_INVEST`;
- credential class = `READ` or `TRADING`;
- credential reference into the local secret store;
- masked broker account identity;
- bound instrument/account environment (`PRODUCTION`, Sandbox handled separately);
- permission/scope class as validated;
- last validation time;
- last successful broker request time;
- health/freshness state;
- token lifecycle state (`unknown`, `valid`, `expired`, `revoked`, `permission_mismatch`, `account_mismatch`, `unavailable`);
- created/rotated/revoked timestamps;
- never raw token.

### CapabilityState

Server-derived product capability snapshot used by Web/Telegram/AI, for example:

- account authenticated;
- READ portfolio capability;
- market data capability;
- Watchtower capability;
- AI capability;
- Telegram capability;
- Shadow capability;
- Real execution capability;
- explicit blocker/reason/recovery action.

The frontend cannot invent this authority from local UI flags.

## 3. READ credential contract

A READ credential is required for portfolio-dependent V10 operation.

### Required properties

- T-Invest read-only permission;
- preferably account-specific when OWNER selects a single intended account and the broker supports it;
- production environment identity distinct from Sandbox;
- token value stored only in runtime local secret store;
- token never used for any broker write method.

### Validation flow

When OWNER provisions/replaces a READ token:

1. authenticated provisioning request reaches the runtime over an approved secure channel;
2. request body is excluded/redacted from logs/traces;
3. backend validates token against T-Invest using non-mutating calls;
4. backend retrieves permitted account list/scope metadata required to prove binding;
5. if multiple accounts are available, OWNER chooses the intended account through masked labels;
6. backend proves the chosen account is accessible;
7. raw token is committed to the local secret store only after validation succeeds (or written to a temporary protected slot then atomically activated);
8. `BrokerConnection` stores only a secret reference + safe metadata;
9. initial refresh job is scheduled;
10. Dashboard remains `partial/onboarding` until portfolio/data-quality gates succeed.

If validation fails, no “connected” success badge is allowed.

## 4. TRADING credential contract

The optional Real credential is a separate account-scoped full-access T-Invest token **without transfer authority**.

It is not an “edit portfolio” credential and is not requested by default onboarding.

### Activation prerequisites

The UI may expose provisioning only after the relevant Block I/Shadow readiness path allows it. Provisioning a token alone must not set Real trading to enabled.

Independent conditions include:

- trading credential valid and bound to intended account;
- master Real kill switch enabled only through reviewed owner/admin flow;
- durable DB/audit state healthy;
- time sync healthy;
- market/freshness requirements healthy;
- accepted Shadow/Real gates;
- exact current immutable plan;
- recent OWNER authentication/confirmation;
- execution policy constraints green.

### Hard isolation

- READ code path never imports/uses the TRADING secret as fallback;
- AI Tool Registry has no access to the TRADING secret or direct broker-write methods;
- Telegram never receives the secret;
- GitHub/CI/self-hosted runner identity cannot read the secret store area containing it;
- browser receives only safe connection status;
- transfer-access token is not accepted as the preferred V10 Real credential; if a token exposes forbidden transfer authority, validation must reject it or require a separately reviewed policy that does not exist in V10.

## 5. Connection states

The Web product must use explicit broker connection states.

### `NOT_CONFIGURED`

READ absent. Show onboarding CTA. Portfolio-specific live content unavailable.

### `VALIDATING`

Credential is being validated. Never show connected/live state yet.

### `READ_READY`

READ valid, account bound, latest required data refresh passes completeness/freshness gate.

### `READ_DEGRADED`

READ exists but broker unavailable/partial/stale. Show last confirmed data time and blocked capabilities.

### `READ_EXPIRED_OR_REVOKED`

Credential cannot authenticate. Disable new portfolio-derived “current” claims; retain historical safe state with clear timestamp; prompt OWNER to replace credential.

### `TRADING_NOT_CONFIGURED`

Normal supported analysis mode. Do not render as an error.

### `TRADING_CONFIGURED_BUT_DISABLED`

Credential exists but Real kill switch/readiness gate is off. Analysis/Shadow continue.

### `REAL_ELIGIBLE`

Credential + safety prerequisites are green. This state does not authorize a trade by itself.

### `REAL_BLOCKED`

One or more prerequisites failed. UI shows exact blocker(s); READ analysis remains available where safe.

### `UNKNOWN_RECONCILING`

A possible Real submit occurred but broker result is ambiguous. Disable repeat submit and reconcile.

## 6. Account / Connections Web UX

Conceptual routes:

```text
/account
/settings/connections
/settings/connections/t-invest
/settings/security
```

Router normalization may change exact paths, but these destinations must exist.

### Account page

- OWNER profile/presentation metadata;
- account security/session shortcut;
- broker connection summary;
- Telegram connection summary;
- AI provider state summary;
- no raw secrets.

### T-Invest connection page

READ card:

- status;
- masked account;
- permission type;
- last validation;
- last successful sync;
- freshness/health;
- actions: connect/replace/revalidate/revoke;
- explanation that READ is required for portfolio monitoring and cannot place orders.

TRADING card:

- clearly **Optional**;
- status and masked account;
- “Real execution disabled/enabled/blocked” status separate from “token exists”;
- actions only when security/readiness permits;
- explicit explanation that every Real plan still requires exact OWNER approval;
- no transfer/margin/short implication.

### Security UX

- password/auth/session/recovery controls according to WP17/WP22A implementation;
- active sessions/revoke where implemented;
- recent-auth requirement surfaced before consequential admin/Real actions;
- failed login/lockout/rate-limit states understandable without leaking account existence.

## 7. Provisioning transport rules

### Local/private Web

During Personal V10, token provisioning should occur through the local/private approved Web surface where practical. HTTPS is required whenever traffic leaves a trusted loopback/private security boundary according to the ingress gate.

### External Web

External token provisioning is forbidden until WP22A security gate is green.

It then requires at minimum:

- TLS with reviewed termination/trusted proxy chain;
- authenticated OWNER session;
- CSRF/origin/host protections where applicable;
- rate limiting/abuse controls;
- request-body logging disabled/redacted for secret endpoints;
- secure no-store response behavior;
- token value never reflected back;
- session step-up/recent auth for TRADING provisioning/revocation.

## 8. Browser-side secret rules

Forbidden:

- `localStorage`;
- IndexedDB;
- service-worker cache;
- URL/query/hash fragments;
- analytics events;
- console logs;
- client crash reports;
- Redux/devtools persisted state;
- clipboard retention beyond explicit user copy before submission.

The token field is cleared immediately after a terminal success/failure state and never repopulated from backend.

## 9. Account binding and multiple T-Invest accounts

If one token can see multiple broker accounts:

- V10 must not silently choose the first account;
- OWNER explicitly selects/binds the intended account through masked identity;
- binding is stored as safe metadata;
- all portfolio/read and optional trading actions verify the same intended account scope;
- a TRADING token bound to a different account than READ blocks Real readiness;
- changing bound account is a consequential configuration change and triggers refresh/reconciliation/revalidation.

## 10. Failure and recovery behavior

### Broker outage

- keep last confirmed snapshot with timestamp;
- show stale/degraded state;
- do not invent current values;
- block Real when freshness/readiness requires current broker evidence.

### Token expiry/revocation

- mark connection invalid;
- notify OWNER according to policy;
- retain non-secret metadata/audit history;
- require explicit replacement;
- never silently try another credential class.

### Secret store failure

- fail closed;
- do not log secret;
- System UI reports credential subsystem unavailable using correlation ID/sanitized error;
- Real blocked.

### Account mismatch

- refuse activation;
- show masked expected vs detected account context where safe;
- require OWNER correction;
- no cross-account fallback.

## 11. Audit requirements

Audit records safe events, not raw credentials:

- credential provision attempt/result;
- connection activated;
- account binding changed;
- validation failure category;
- credential replaced/rotated/revoked;
- Real credential readiness transition;
- kill-switch transition;
- OWNER/session actor;
- correlation ID and timestamp.

Never audit token text, Authorization metadata, full account ID or private broker payload solely for diagnostics.

## 12. API/capability contract direction

Exact endpoint names are owned by the implementing WP, but Web requires canonical server contracts equivalent to:

- current OWNER/profile;
- session/security status;
- capability state;
- broker connection metadata;
- provision/replace/revoke credential (write-only secret input);
- validate/revalidate connection;
- list/select allowed masked broker account identity;
- observable portfolio refresh job;
- current data freshness/completeness.

Consequential POST operations require idempotency/correlation rules where retries could cause duplicate state changes.

## 13. Acceptance tests

At minimum:

1. no READ -> login works, System/Account works, portfolio live claims unavailable;
2. valid READ -> account bind -> initial sync -> Portfolio ready;
3. read-only token cannot submit order;
4. invalid/expired READ -> clear invalid state, no fallback to TRADING;
5. multiple accounts -> no implicit first-account selection;
6. READ account != TRADING account -> Real blocked;
7. no TRADING -> full analytical product remains healthy;
8. provisioned TRADING with Real switch off -> broker writes impossible;
9. AI/Telegram cannot retrieve raw credential;
10. browser storage scan finds no token;
11. server logs/crash diagnostics contain no token;
12. double provision/revoke request is safe/idempotent where required;
13. token rotation preserves correct account binding or forces explicit rebinding;
14. broker outage produces stale/degraded UI, not fake current data;
15. ambiguous possible submit never enables repeat submit;
16. logout/session expiry prevents account/secret management and Real approval;
17. external provisioning endpoint is unavailable before ingress/auth gate;
18. credential revocation downgrades capability state without breaking unrelated System UI.

## 14. Definition of Done

This contract is satisfied only when OWNER can securely operate the V10 account and T-Invest connection lifecycle through the accepted product without GitHub edits, secret leakage, hidden credential switching or ambiguous broker authority.
