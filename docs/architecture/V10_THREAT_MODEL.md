# Omni-CIO V10 — Threat Model

Status: **WP22A clientless external-access threat-model update**  
Scope: Personal V10 platform, current V9 coexistence, future Lenovo/Web/Telegram/AI/Real contours.

## 1. Security objective

A defect, compromised interface, malicious document, stolen session, CI mistake or AI hallucination must not silently become uncontrolled movement of real money or disclosure of broker secrets/private portfolio data.

Primary safety strategy:

**separate authority -> validate evidence -> fail closed -> explicit owner approval -> idempotent submit -> broker reconciliation -> auditable recovery**.

## 2. Protected assets

Highest priority assets:

- Real trading credential and broker authority;
- read-only broker credential;
- Telegram bot credential;
- local encryption/recovery keys;
- private portfolio/balance/operations data;
- immutable plan/approval state;
- execution idempotency and reconciliation state;
- Decision Journal/audit evidence;
- canonical GitHub source/release identity;
- V9 recovery assets;
- V10 database/backups;
- AI System Policy/Tool Registry and model provenance.

## 3. Trust boundaries

1. GitHub repository <-> CI runner.
2. CI/deployment <-> Lenovo runtime.
3. Runtime services <-> local secret store.
4. Web/Telegram <-> OWNER identity/session.
5. AI/RAG <-> untrusted retrieved text.
6. Research Collector <-> public Internet/sources.
7. Core <-> broker read APIs.
8. Execution service <-> T-Invest Real API.
9. Runtime DB <-> backup/off-device recovery.
10. Current V9 runtime <-> future V10 replacement boundaries.
11. Authenticated Web provisioning <-> connection-scoped read-broker secret child.
12. OWNER browser <-> Cloudflare Access/edge <-> Cloudflare Tunnel/cloudflared <-> loopback-only Web origin.

## 4. Threat catalogue

### T1 — Repository or workflow compromise

**Scenario:** malicious/accidental workflow code executes on self-hosted runner and attempts to read secrets or modify production.

Controls planned:

- private repository;
- focused PR/review/CI discipline;
- separate runner/runtime identities;
- runner denied trading-secret/private-backup access;
- reviewed release/deploy identity;
- workspace cleanup;
- branch/ruleset protection evaluation in WP3;
- secret scanning/SAST/dependency audit.

Fail-safe: inability to prove reviewed release identity blocks privileged deployment.

### T2 — Direct push / bypass of review

**Scenario:** repository allows an authorized user to bypass normal PR discipline.

Current observation at WP0: server-side branch protection is not enabled on `main`.

Interim control: manual no-direct-main policy plus required focused PR and exact-head Regression Shield.

WP3 action: evaluate/configure strongest protection available for the owner's GitHub plan and document compensating controls when a platform feature is unavailable.

### T3 — Secret leakage

**Scenario:** token appears in Git, logs, crash dump, UI, prompt, diagnostic archive or process arguments.

Controls:

- local secret store;
- process/role ACL;
- redaction/allowlist logging;
- no secrets in CLI args/history;
- repository secret scan;
- crash-dump policy;
- separate rotation/revocation procedure.

Response: revoke/rotate affected credential; treat uncertain exposure as compromised.

### T4 — Stolen or lost Lenovo/SSD

**Scenario:** attacker obtains powered-off device/storage.

Controls planned:

- full-disk or owner-approved equivalent encryption;
- separate recovery-key custody;
- runtime secret protection;
- no plaintext backups;
- minimal local privilege.

Exit requirement later: physical loss of powered-off disk does not trivially disclose broker secrets/private DB.

### T5 — Web session compromise

**Scenario:** stolen cookie/session/deep link is used to view data or approve action.

Controls planned:

- TLS when external ingress exists;
- server-side sessions;
- secure/HttpOnly/SameSite or reviewed equivalent;
- rotation/revocation/expiry;
- CSRF/Origin/Host/CORS controls;
- rate limiting;
- recent/step-up OWNER authentication for Real plan approval;
- plan hash binding.

Fail-safe: external Real approval surface remains disabled before WP22A passes.

### T6 — Telegram impersonation/replay

**Scenario:** attacker forges client fields or replays stale Mini App auth data.

Controls planned:

- server-side validation of Telegram `initData`;
- OWNER allowlist;
- `auth_date` freshness;
- replay/session handling;
- Telegram identity does not reveal broker secret and is not sole proof for Real approval.

### T7 — Prompt injection / poisoned RAG

**Scenario:** a news article/document tells the model to ignore policy, call privileged tools, reveal data or alter a recommendation.

Controls:

- retrieved content is untrusted data, not instructions;
- immutable higher-priority System Policy;
- allowlisted Tool Registry;
- AI denied broker write and secret access;
- source provenance/identity/freshness;
- RAG poisoning/adversarial evals;
- structured output validation;
- unknown/abstain on insufficient evidence.

### T8 — AI hallucination / overconfidence

**Scenario:** model invents an event, issuer, figure or recommendation.

Controls:

- source-grounded facts only;
- AI output clearly separated from canonical evidence;
- deterministic Credit/Risk/Optimizer/Plan authority;
- confidence/unknowns/contradictions;
- model/eval versioning;
- no direct execution.

### T9 — Wrong instrument identity

**Scenario:** news or ticker string maps to wrong security/issuer and alters portfolio decision.

Controls:

- broker UID/FIGI/ISIN/class-code primary identity;
- name/ticker only secondary labels;
- identity binding on evidence;
- ambiguity blocks strong conclusion.

### T10 — Stale/incomplete/contradictory data

**Scenario:** old market quote or partial portfolio/evidence is treated as exact current truth.

Controls:

- timestamps/freshness contracts;
- completeness state;
- contradiction state;
- stale market blocks exact sizing/Real preflight;
- explicit degraded/unknown states.

### T11 — Duplicate/ambiguous broker submit

**Scenario:** timeout occurs after possible broker acceptance and software retries automatically.

Controls inherited from V9:

- UUID/idempotency binding;
- at most one possible submit per request identity;
- ambiguous submit -> UNKNOWN / do-not-resubmit;
- broker reconciliation only;
- submitted != filled without proof.

This is a P0 invariant.

### T12 — Plan drift after approval

**Scenario:** instrument/lots/limits/market conditions change after owner approved a plan.

Controls:

- immutable plan hash;
- short expiry;
- repeat preflight before every leg;
- material drift invalidates approval;
- new plan requires new approval.

### T13 — Privilege escalation between services

**Scenario:** compromised Web/AI/Telegram process reaches Real credential or OS admin.

Controls planned:

- separate service identities;
- least filesystem/secret ACL;
- execution service as narrow capability boundary;
- negative permission tests;
- no general command shell exposed to AI.

### T14 — Database corruption / state loss

**Scenario:** SSD failure/corruption loses plan/execution/reconciliation/audit state.

Controls planned:

- PostgreSQL migrations/constraints;
- append-only/audit-sensitive semantics;
- encrypted backups with hashes;
- RPO/RTO;
- restore rehearsal;
- Real submit blocked if durable state/audit persistence unhealthy.

### T15 — Clock manipulation/drift

**Scenario:** wrong local time breaks freshness, session expiry or plan confirmation lifetime.

Controls planned:

- Windows/NTP monitoring;
- UTC canonical timestamps;
- source/broker/local receive times kept distinct;
- unsafe drift blocks time-sensitive approval/Real operations.

### T16 — Dependency/supply-chain compromise

**Scenario:** malicious/compromised package/action/model artifact is installed.

Controls:

- hash-locked Python dependencies;
- lockfiles and exact toolchain policy;
- pinned GitHub Actions;
- dependency audit/SAST;
- model digest/source/license registry;
- controlled updates and rollback;
- no silent AI model auto-update changing Real behavior.

### T17 — Unsafe external data retrieval

**Scenario:** parser executes active content, source changes format, rate-limit bypass or unapproved scraping creates bad evidence/security risk.

Controls planned:

- trusted source registry;
- approved retrieval methods;
- safe parser/normalization;
- no active HTML/JS execution;
- parser version/content hash;
- rate limits/cache;
- terms/license/retention review.

### T18 — Excessive monitoring / alert flood

**Scenario:** noisy Watchtower produces repeated alerts or AI jobs, hiding true incidents and exhausting resources.

Controls planned:

- deterministic materiality triggers;
- semantic dedup;
- severity policy;
- bounded retries/jobs;
- resource/temperature limits;
- AI wakes only for qualified tasks.

### T19 — Unauthorized architecture drift

**Scenario:** developer creates second frontend/Gateway/AI/execution stack or account-only hidden configuration.

Controls:

- Program Lock;
- current-WP scope;
- repository structure guards in WP1/WP3;
- ADR process;
- Account Independence invariant;
- one source of truth.

### T20 — V9 regression during V10 migration

**Scenario:** V10 refactor breaks accepted current production or recovery before replacement is accepted.

Controls:

- V9 remains deployed/protected;
- golden regression fixtures;
- compatibility wrappers until proof;
- current `app:app` contract retained;
- package-specific staged acceptance;
- explicit rollback.

### T21 — Web broker READ credential provisioning abuse

**Scenario:** a stolen Web session, malicious client request, broad T-Invest credential, path traversal or compromised CI attempts to store/read/replace a broker credential outside the authenticated tenant READ boundary.

WP17 controls:

- normal broker credential entry exists only under an authenticated same-origin Web session;
- client-supplied tenant/account ownership claims are ignored; tenant scope comes only from the server-side session;
- candidate token is sent in a request body, never URL/CLI/Web Storage, and is not returned in API responses;
- preview material is memory-only, short-lived, scoped to user+tenant and zeroed on consume/cancel/expiry;
- accepted WP15 `GetAccounts` validation must prove READ-only authority before durable storage; FULL/unknown authority fails closed;
- broad READ token may expose several accounts but the user binds only verified masked accounts from that exact challenge;
- replacement must preserve the same verified account set rather than silently rebinding a connection;
- durable secret bytes use the existing WP8 DPAPI LocalMachine mechanism under `read-broker/connections`, never PostgreSQL;
- runtime write authority is limited to that READ child; `broker_trading` and execution credentials remain unreachable;
- opaque random secret references prevent broker account IDs from becoming filesystem paths;
- runner has no secret `ReadData`/write/delete authority and cannot upload the secret subtree as evidence;
- public registration and Internet ingress remain disabled; external hardening is still owned by WP22A.

Fail-safe: missing/invalid vault marker or ACL, stale/invalid challenge, tenant mismatch, broker authority mismatch, database persistence failure or credential-store failure rejects the provisioning action and never falls back to TRADE/write credentials.

### T22 — Clientless external Web boundary bypass or misconfiguration

**Scenario:** a forged Cloudflare identity header, unprotected tunnel route, hostile Host/Origin, stolen remote session, compromised CI runner, provider drift or failed rollback bypasses the intended OWNER-only external Web gate or leaves the Lenovo origin exposed.

WP22A controls:

- the Lenovo Web origin binds only to `127.0.0.1`; no inbound public Lenovo port is introduced;
- Cloudflare Tunnel uses a single reviewed hostname plus catch-all `http_status:404`;
- Cloudflare Access is deny-by-default and the selected Access application/policy is created before DNS publication is considered usable;
- `cloudflared` is configured to validate `Cf-Access-Jwt-Assertion` for the exact team/application audience before proxying the protected hostname;
- the application additionally requires the expected Access identity fingerprint, non-empty assertion, exact external Host, loopback peer, server-side Omni-CIO session, exact HTTPS Origin for unsafe requests and matching CSRF cookie/header;
- external sessions use bounded idle/absolute lifetimes, rotation/revocation, Secure/HttpOnly/SameSite session cookies and no Web Storage credentials;
- login and mutation rates are bounded and external responses use HSTS/CSP/frame/object/referrer/cache hardening;
- the self-hosted GitHub runner is denied direct loopback TCP access and denied runtime config/tunnel-token access by OS controls;
- provider credentials are unavailable to arbitrary PR code; real provider mutation is allowed only from reviewed accepted `main` through the protected Phase B contour;
- tunnel token, raw OWNER identity, broker secrets and private portfolio data remain outside GitHub/CI artifacts;
- Phase B apply is ordered fail-closed; after a late failure rollback removes/disables external reachability first and reconstructs the previously accepted local Web;
- separate ordinary-phone browser evidence is mandatory and cannot be synthesized by CI.

Local-trust note: Cloudflare Access is not treated as a defense against an already-compromised OWNER/admin Windows account. Such local code execution is a node compromise governed by T3/T13 and the disk/runtime controls. The explicitly less-trusted CI runner is isolated from the loopback origin and WP22A secret/config subtrees.

Fail-safe: missing Access validation, wrong OWNER identity, wrong Host/Origin/CSRF, non-loopback origin path, missing runner denial, provider-state mismatch or rollback uncertainty blocks WP22A acceptance and keeps WP23 LOCKED.

## 5. Severity

- **P0 — money/security authority:** possible unauthorized/duplicate Real action, secret disclosure, approval bypass. Stop current work.
- **P1 — data correctness/recovery:** wrong financial facts, identity, lost durable state, unrecoverable backup. Next WP blocked.
- **P2 — functional reliability:** broken feature without authority/data compromise. Fix current WP.
- **P3 — cosmetic/minor:** may enter backlog if Exit Gate permits.

## 6. Security acceptance philosophy

No single control is considered sufficient. Real-money safety depends on defense in depth:

`identity + least privilege + evidence + deterministic constraints + immutable approval + idempotency + reconciliation + audit + recovery`.

## 7. Threat-model maintenance

Every V10 WP that introduces a new external surface, credential, persistent state, AI tool or Real authority must update this threat model or explicitly state why no threat boundary changed.
