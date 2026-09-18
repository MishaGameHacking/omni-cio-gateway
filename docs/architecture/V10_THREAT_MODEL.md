# Omni-CIO V10 — Threat Model

Status: **UPDATED FOR PUBLIC-HOSTED MULTI-USER TARGET / WP22A PLANNING**  
Scope: protected V9 coexistence, public hosted Web/account/tenant target, future Telegram/AI/Real contours.

## 1. Security objective

A defect, compromised interface, malicious document, stolen session, cloud/CI mistake, cross-tenant authorization bug or AI hallucination must not silently become:

- disclosure of another USER's private state or broker credential;
- unauthorized/duplicate real-money action;
- provider/engineering identity becoming product authority;
- public-service dependency on PROJECT OWNER home infrastructure;
- unsafe public activation before broker/legal/security gates.

Primary strategy:

**separate authority -> tenant isolation -> validate evidence -> fail closed -> explicit USER approval for own tenant -> idempotent submit -> broker reconciliation -> auditable recovery**.

## 2. Protected assets

Highest priority assets include:

- each tenant's READ/optional TRADE credentials and verified broker-account bindings;
- tenant-private positions/balances/operations/reports/decisions/plans/research;
- server-side session/account-linking state;
- immutable plan/approval/idempotency/reconciliation state;
- audit/Decision Journal evidence;
- cloud runtime/data/secret credentials and encryption/recovery keys;
- Telegram/VK/provider secrets;
- canonical GitHub source/release identity;
- V9 recovery assets;
- PostgreSQL/backups;
- AI System Policy/Tool Registry/model provenance.

## 3. Trust boundaries

1. GitHub repository <-> CI runner.
2. CI/release <-> managed-cloud production runtime.
3. Runtime services <-> tenant private-data/secret plane.
4. Public browser <-> edge/reverse proxy <-> Web/API.
5. Product authentication provider <-> internal Omni-CIO account/session.
6. USER session <-> tenant authorization / database isolation.
7. Core <-> tenant BrokerConnection READ APIs.
8. Execution service <-> same-tenant TRADE credential / T-Invest Real API.
9. Runtime DB <-> encrypted backup/off-runtime recovery.
10. AI/RAG <-> untrusted retrieved/tenant data.
11. Research collector <-> public Internet/sources.
12. Current V9 runtime <-> future V10 cutover.
13. PROJECT OWNER engineering/provider authority <-> ordinary product USER authority.
14. Cloud edge/provider identity <-> Omni-CIO product authentication.

## 4. Threat catalogue

### T1 — Repository/workflow compromise

**Scenario:** malicious/accidental workflow code executes on CI and tries to read production secrets or mutate production.

Controls: private repo, exact-head PR/CI, runner/runtime separation, no production tenant secrets in arbitrary PR jobs, reviewed privileged deployment boundary, workspace cleanup, source/release identity verification, secret scan/SAST/dependency audit.

Fail-safe: inability to prove reviewed accepted source blocks privileged deployment.

### T2 — Review/protection bypass

**Scenario:** direct push or bypass defeats normal engineering review.

Controls: protected main/ruleset where available, focused PR, required exact-head all-GREEN checks, zero blockers, squash merge and post-merge Regression Shield. GitHub engineering authority still does not create product/trading authority.

### T3 — Secret leakage

**Scenario:** broker/provider/Telegram/VK/encryption secret appears in source, logs, crash data, browser response/storage, prompts or artifacts.

Controls: tenant-scoped secret store/encryption, redaction/allowlist logging, no browser secret return/Web Storage, no CLI/history leakage, CI secret scan, least-privilege access, rotation/revocation.

Response: uncertain exposure is treated as compromise and credential is revoked/rotated.

### T4 — Stolen/lost engineering device

**Scenario:** attacker obtains Lenovo/storage.

Controls: disk/runtime protection and minimal privilege. More importantly, Lenovo is no longer the final public production/private-state authority; ordinary public service availability and hosted tenant secrets must not depend on the OWNER laptop.

### T5 — Web session compromise

**Scenario:** stolen/fixed/replayed session accesses a USER tenant or approves action.

Controls: TLS, server-side sessions, Secure/HttpOnly/SameSite cookies, fixation protection, rotation/revocation/expiry, CSRF/Origin/Host/CORS, rate limits, recent/step-up USER auth for Real approval and immutable plan binding.

### T6 — Cross-tenant IDOR / authorization confusion

**Scenario:** USER A supplies Tenant B/object/job/cache identifiers and receives or mutates B's state.

Controls: tenant scope from server-side session only; object ID is never authority; application authorization plus database-enforced tenant isolation; tenant-scoped foreign keys/uniqueness; negative IDOR tests.

Fail-safe: ambiguous/missing tenant binding denies access.

### T7 — Cross-tenant background/cache/RAG leakage

**Scenario:** worker, cache key, notification, export, AI/RAG memory or audit record loses tenant scope and leaks data.

Controls: immutable tenant scope on jobs/checkpoints, tenant-aware cache keys/storage, scoped RAG namespaces, explicit USER/tenant context on notifications/exports, cross-scope regression tests.

### T8 — Backup/restore tenant collapse

**Scenario:** restore mixes tenant rows, secret bindings or session/account ownership.

Controls: encrypted backups, integrity hashes/corrupt-backup rejection, schema/tenant constraints, restore rehearsal, cross-tenant post-restore negatives, replacement-runtime recovery.

### T9 — Edge/provider identity becomes product identity

**Scenario:** Cloudflare/GitHub/provider account membership automatically mints a product session or selects privileged tenant.

Controls: provider identity remains engineering/staging authority only; product session requires Telegram/VK -> internal Omni-CIO account binding; PROJECT OWNER uses same USER path; no OWNER fingerprint/hard-coded owner tenant bootstrap.

### T10 — Home-origin availability dependency

**Scenario:** public service is exposed through a tunnel but its sole origin is OWNER home Lenovo/network; power/ISP/router failure takes all users offline.

Controls: final production origin is approved managed-cloud runtime; no home public IP/Wi-Fi/router/LAN/Lenovo dependency; recovery/redeploy works without OWNER home access.

A Cloudflare Tunnel can be an origin-protection transport, but a home-Lenovo sole origin fails this gate.

### T11 — Prompt injection / poisoned RAG

**Scenario:** retrieved or tenant-provided text asks model to ignore policy, reveal secrets or call privileged tools.

Controls: retrieved content is untrusted data; immutable System Policy; allowlisted typed tools; AI denied raw broker secrets/write/admin; provenance/freshness; adversarial evals; structured validation/abstain.

### T12 — AI hallucination / wrong instrument / stale data

**Scenario:** model invents facts or maps evidence to wrong instrument, stale quote or incomplete portfolio.

Controls: deterministic Core authority, canonical IDs, source identity/provenance/timestamps, confidence/contradiction/completeness states, AI output separated from canonical evidence, stale data blocks unjustified exact sizing/Real preflight.

### T13 — Duplicate/ambiguous broker submit

**Scenario:** timeout follows possible broker acceptance and software retries automatically.

Controls: UUID/idempotency binding, at most one possible submit per identity, ambiguity -> UNKNOWN/do-not-resubmit, broker reconciliation only, submitted != filled without proof.

P0 invariant.

### T14 — Plan drift after USER approval

**Scenario:** plan/instrument/lots/limits/material market state changes after approval.

Controls: immutable plan hash, short expiry, recent/step-up USER auth, repeat preflight, material drift invalidates approval and requires new plan/approval.

### T15 — Privilege escalation between services

**Scenario:** Web/AI/Telegram/background process reaches tenant secrets, execution authority or cloud admin.

Controls: separate least-privilege identities/capabilities; narrow secret/decryption paths; negative permission tests; no general admin shell to AI; future execution as narrow capability boundary.

### T16 — Database corruption/state loss

**Scenario:** corruption loses plan/execution/audit/tenant state.

Controls: PostgreSQL constraints/migrations, encrypted hashed backups, RPO/RTO, restore rehearsal, durable-state readiness; Real submit blocked if required durable state/audit persistence is unhealthy.

### T17 — Clock manipulation/drift

**Scenario:** incorrect time breaks session/freshness/approval lifetime.

Controls: provider/NTP monitoring, UTC canonical timestamps, source/broker/receive timestamps distinct; unsafe drift blocks time-sensitive approval/Real operations.

### T18 — Dependency/supply-chain compromise

**Scenario:** compromised package/Action/model/tool/provider image is installed.

Controls: locks/hashes/pins, dependency audit/SAST, reviewed toolchain/image provenance, controlled update/rollback, model digest/source/license registry.

### T19 — Unsafe external data retrieval / terms violation

**Scenario:** parser executes active content, scraper violates terms, or external source behavior creates security/legal risk.

Controls: source registry, safe parse/normalization, no active untrusted HTML/JS execution where not explicitly sandboxed, content hashes/parser versions, bounded rate/cache, terms/license/retention review.

### T20 — Public T-Invest service used without permission

**Scenario:** public users submit their own tokens and product assumes this automatically grants right to operate a public T-Invest-based service/retransmit data.

Controls: public Web/account activation separated from T-Invest connector activation; current official broker-terms gate remains fail-closed; no UI/status claim without contractual evidence; connector may remain disabled while public account platform exists.

### T21 — Tenant broker credential abuse

**Scenario:** stolen USER session, malicious client, broad credential or implementation bug stores/reads/reuses a credential outside that tenant.

Controls:

- authenticated same-origin USER settings only;
- server session supplies tenant scope;
- candidate token body only, never URL/Web Storage;
- raw token not returned;
- verified broker authority/account binding before durable use;
- encrypted tenant-scoped secret record/reference;
- no global/shared credential fallback;
- no Cortex/CI/unrelated tenant access;
- replacement/revocation semantics preserve verified binding;
- optional TRADE remains separate from READ.

### T22 — READ/TRADE account mismatch

**Scenario:** TRADE credential exposes an account not independently present under verified READ authority, or credentials belong to different tenants.

Controls: exact same-tenant intersection `VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS`; mismatch fails closed; account IDs masked; no automatic promotion/rebinding.

### T23 — Public ingress/session/CSRF/Host abuse

**Scenario:** hostile Host/Origin, direct API call, stolen session, forged proxy headers, weak CORS or rate-limit bypass reaches tenant data.

Controls: exact public hostname/TLS, trusted proxy/protocol boundary, Host allowlist, CSRF + Origin/Referer, deny-by-default CORS, bounded rate limits, secure session cookies, direct API negative tests, security headers and no edge-identity bypass.

### T24 — Cloud/runtime secret or backup compromise

**Scenario:** cloud admin/runtime role/backup path exposes all tenant secrets/data.

Controls: least-privilege runtime identities, encryption at rest, separation of secrets/private rows where appropriate, auditable access/rotation, encrypted off-runtime backups, bounded retention, no source/CI secret material, incident/revocation/recovery procedure.

### T25 — Provider outage / lock-in / failed recovery

**Scenario:** cloud region/provider fails or account is lost and product cannot recover.

Controls: documented provider/data inventory, GitHub source/release provenance, encrypted off-runtime recovery, replacement-runtime rehearsal, rollback, export/exit path and measured RPO/RTO. OWNER home infrastructure is not the production fallback assumption; protected V9 remains separate recovery history until its owning cutover/decommission.

### T26 — Unsafe free-public abuse / resource exhaustion

**Scenario:** free registration/public endpoint attracts brute force, scraping, bot accounts, expensive research/AI jobs or DB exhaustion.

Controls: registration/login/API rate limiting, abuse controls, quotas/bounded background jobs, backpressure/circuit breakers, capacity/load tests, monitoring and graceful degradation. Security/money gates remain fail-closed.

Free access does not mean unbounded resource authority.

### T27 — Premature monetization or entitlement drift

**Scenario:** old trial/subscription code blocks initial free users or payment logic is introduced without OWNER/legal decision.

Controls: initial flags `BILLING_ENABLED=false`, `TRIAL_ENABLED=false`, `SUBSCRIPTION_ENFORCEMENT=false`, `PREMIUM_FEATURE_GATING=false`; future monetization `DEFERRED_OPTIONAL` and separately amended/tested.

### T28 — Unauthorized architecture drift

**Scenario:** developer/AI creates second frontend/Gateway/Core/identity/broker stack or returns to OWNER-only/home-production assumptions.

Controls: Program Lock, Amendments Index, current status, Public Hosted machine contract, repository/documentation/public-product guards, current-WP scope and ADR/amendment process.

### T29 — V9 regression during V10 migration

**Scenario:** V10 changes break accepted V9 production/recovery before cutover.

Controls: protected `app:app`, compatibility wrappers/tests, staged acceptance, explicit rollback and owning parity/decommission gate.

## 5. Severity

- **P0 — money/security authority:** unauthorized/duplicate Real action, secret disclosure, cross-tenant private-data disclosure, approval bypass. Stop current work.
- **P1 — data correctness/recovery/identity:** wrong financial facts/tenant binding, lost durable state, unrecoverable backup, unsafe public auth. Next acceptance blocked.
- **P2 — functional reliability:** broken feature without authority/data compromise. Fix current WP.
- **P3 — cosmetic/minor:** backlog only if Exit Gate permits.

## 6. Security acceptance philosophy

No single edge, session, database or broker control is sufficient.

Defense in depth:

`product identity + tenant isolation + least privilege + evidence + deterministic constraints + immutable approval + idempotency + reconciliation + audit + recovery`.

Public target does not equal public activation. `PUBLIC_MULTI_USER_ENABLED=false`, `trading_methods=false` and `REAL_TRADING_ENABLED=false` remain until their owning accepted gates change them.

## 7. Threat-model maintenance

Every V10 WP that introduces a new public surface, tenant data path, credential, persistent state, AI tool, provider or Real authority must update this threat model or explicitly demonstrate why no threat boundary changed.


## Telegram Login production-activation preparation — 2026-09-18

The accepted Telegram/VK authentication implementation is being prepared for canonical
Cloudflare runtime activation without changing its current `BLOCKED_EXTERNAL` state.

Additional controls for this activation contour:

- Cloudflare Worker secret bindings are passed to the production Container only through
  an explicit source-controlled provider-auth allowlist; staging receives no provider
  credential bindings from this path;
- the Worker never logs or serializes provider secret values;
- public browser Origin authority (`omnicio.ru`) is separate from the fixed internal
  Container Host (`omni-cio.internal`), preventing the internal proxy boundary from
  accidentally rejecting the canonical browser while still rejecting foreign origins;
- `PUBLIC_MULTI_USER_ENABLED=false` remains the source-controlled production default;
- new external identity registration is enabled only when that exact public-user flag is
  accepted as `true`; provider secrets alone cannot activate registration or mint a
  tenant;
- the PROJECT OWNER still uses the ordinary USER path and the historical owner scope
  remains ineligible for Telegram/VK external identity binding;
- broker write, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, transfer,
  withdrawal, margin, leverage and uncovered-short boundaries are unchanged.
