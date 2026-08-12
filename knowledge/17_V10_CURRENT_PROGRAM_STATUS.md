# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-12

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / BLOCK C COMPLETE / WP15 CODE+SECURITY+LIVE SUPPORT ACCEPTED / WP17 COMPLETE / OWNER LIVE ACCEPTANCE REQUIRED NEXT / WP18 LOCKED**.

Accepted implementation progress remains **26%**.

Block C's full 12% weight is accepted. Block D is deliberately **not credited** yet: WP11–WP14 are complete, WP15 implementation/code/security is accepted, and the dedicated deferred-live Web support path has now also been repository-accepted. The OWNER-approved Identity / Multi-Tenant Account / Authentication Amendment still requires the real T-Invest READ acceptance to be completed through the reviewed authenticated Web broker-provisioning flow delivered by WP17.

WP16 and WP17 are repository-accepted through exact-head PR review, required Lenovo CI, squash merge and exact-main post-merge Regression Shield. Block E remains in progress and is not credited piecemeal before its own Block Exit Gate.

The dedicated deferred-WP15 live support implementation from PR #284 and focused hardening through PR #299 are accepted. The latest accepted runtime/operational implementation baseline before this status synchronization is `6bd4e2c683386269ee573f25f50cbc8780ac9ff5`. The exact OWNER checkout SHA is intentionally not hard-coded here: it must be the current `main` after this status transition itself is merged and its required post-merge gates are GREEN. Product/live support was last exercised after PR #298 on `bc5842e019ffa5c612b1a0b6cffe00e9c5d2718a`: Regression Shield #1481 / run `31620202000`, WP15 Live Web Support Audit #106 / run `31620202006`, WP16 Web Design System Audit #205 / run `31620202052`, and WP17 Application Shell Audit #176 / run `31620202030` are GREEN; WP15 OWNER Audit #14 / run `31620201999` remains intentionally `OWNER_ACTION_REQUIRED` because real OWNER live evidence does not exist yet. PR #299 then hardened only the self-hosted Windows runner diagnostic/recovery path; exact-head Self-Hosted Windows CI #874 / run `31627886479`, WP16 #221 / run `31627886484`, and WP17 #192 / run `31627886513` are GREEN, while hosted Fast PR Checks #782 and Toolchain Compatibility #817 did not start because of the existing GitHub account billing/spending-limit condition and remain infrastructure failures, not PASS. After squash merge of PR #299, exact-main Regression Shield #1482 / run `31629149440`, WP16 #222 / run `31629149358`, and WP17 #193 / run `31629149359` are GREEN.

The next authorized dependency gate is **the real deferred WP15 live broker READ acceptance through the accepted local/private WP17 `Settings -> Broker Connections` flow**. WP18 implementation remains unauthorized until that evidence and the independent non-admin runner audit pass according to the amendment and Master Plan; WP18 real-data acceptance remains explicitly locked.

The live gate must prove, for the authenticated tenant/BrokerConnection:

- READ_ONLY broker authority;
- intended broker-account selection using masked outward identity only;
- portfolio-summary parity;
- one sample-position quantity/value parity;
- acceptable freshness;
- sanitized evidence bound to the reviewed implementation.

No real T-Invest token, full account ID or private portfolio payload may be placed in GitHub, CI, chat, logs or artifacts. The normal credential entry point is the authenticated Web UI, not PowerShell.

Owner action required now: **YES — only the non-delegable local/private live-acceptance procedure remains.** Engineering has accepted the support path and its post-merge code/security gates. The OWNER must start the temporary acceptance runtime from the exact accepted `main`, enter the existing READ token only inside the loopback Web `Settings -> Broker Connections` flow, verify the masked/parity/freshness facts locally, finalize sanitized evidence, and then allow the independent non-admin OWNER audit to be rerun on the same implementation. If the local procedure exposes another implementation defect, engineering must fix that defect through a focused PR before any retry.

Owner start command: **`START V10`** received 2026-08-05.

Starting or advancing V10 never expands broker/Real-money authority by itself.

## Accepted / current WP state

- Block A / WP0 — **COMPLETE (5%)**;
- Block B / WP1 — **COMPLETE**;
- Block B / WP2 — **COMPLETE**;
- Block B / WP3 — **COMPLETE**;
- Block B / WP4 — **COMPLETE (Block B accepted at 9%)**;
- Block C / WP5 — **COMPLETE**;
- Block C / WP6 — **COMPLETE**;
- Block C / WP7 — **COMPLETE**;
- Block C / WP8 — **COMPLETE**;
- Block C / WP9 — **COMPLETE**;
- Block C / WP9A — **COMPLETE**;
- Block C / WP10 — **COMPLETE (Block C accepted at 12%)**;
- Block D / WP11 — **COMPLETE**;
- Block D / WP12 — **COMPLETE**;
- Block D / WP13 — **COMPLETE**;
- Block D / WP14 — **COMPLETE**;
- Block D / WP15 — **IMPLEMENTATION / CODE / SECURITY / LIVE SUPPORT ACCEPTED; REAL OWNER BROKER EVIDENCE STILL REQUIRED**;
- Block E / WP16 — **COMPLETE**;
- Block E / WP17 — **COMPLETE**;
- Block E / WP18+ — **LOCKED behind owning dependencies and Master Plan sequence**;
- WP18 real-data acceptance — **LOCKED behind deferred WP15 real live evidence**;
- public multi-user activation — **OFF / LOCKED**;
- public Internet ingress — **OFF / LOCKED until its owning security gate**;
- broker write / Real execution — **UNCHANGED / NOT AUTHORIZED by this status transition**.

## Canonical authority

Base program:

- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`;
- `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`.

Accepted planning amendments are indexed by:

- `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`.

The current WP15/WP17/WP18 sequencing is additionally governed by the accepted OWNER amendment:

- `docs/master-plan/OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md`;
- `docs/architecture/ADR-0010-identity-multitenant-authentication.md`;
- `docs/architecture/V10_IDENTITY_AUTHENTICATION_CONTRACT.json`;
- `docs/operations/V10_IDENTITY_AND_BROKER_CONNECTION_SECURITY_NOTES.md`;
- `docs/architecture/V10_WP15_TINVEST_READONLY_CONTRACT.md`;
- `docs/architecture/V10_WP15_LIVE_ACCEPTANCE_STATE.json`;
- `docs/architecture/V10_WP15_LIVE_WEB_ACCEPTANCE_CONTRACT.json`;
- `docs/operations/V10_WP15_OWNER_LIVE_READ_RUNBOOK.md`;
- `docs/architecture/V10_WP16_WEB_DESIGN_SYSTEM_CONTRACT.md`;
- `docs/architecture/ADR-0011-web-read-credential-provisioning.md`;
- `docs/architecture/V10_WP17_APPLICATION_SHELL_CONTRACT.json`;
- `docs/operations/V10_WP17_APPLICATION_SHELL_RUNBOOK.md`.

Binding execution/navigation sources also include:

- `AGENTS.md`;
- `README.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` for protected V9 runtime state;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `docs/master-plan/OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md`;
- accepted architecture/security/recovery/operations contracts.

GitHub remains engineering source of truth. The protected production/recovery baseline remains **Omni-CIO v9.0.0 — COMPLETE / owner-accepted / controlled maintenance** until the responsible later V10 parity/decommission gate.

## Progress

| Block | Planned weight | Accepted state |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | COMPLETE — WP1 / WP2 / WP3 / WP4 |
| C. Lenovo Omni-CIO Node / infrastructure | 12% | COMPLETE — WP5 / WP6 / WP7 / WP8 / WP9 / WP9A / WP10 |
| D. V10 Core and data | 14% | IMPLEMENTATION + LIVE SUPPORT ACCEPTED THROUGH WP15; REAL OWNER LIVE EVIDENCE REQUIRED / BLOCK CREDIT WITHHELD |
| E. Omni-CIO Web Platform | 14% | IN PROGRESS — WP16 COMPLETE / WP17 COMPLETE / WP18 LOCKED |
| F. Telegram | 8% | NOT STARTED — product/interaction contract pre-approved only |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED — autonomous portfolio-governance role pre-approved only |
| I. Personal Real Execution | 7% | NOT STARTED — cash-only confirmed execution policy pre-approved only |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED — commercial/license/update/legal-gate planning pre-approved only |
| **TOTAL** | **100% planned** | **26% ACCEPTED** |

The 26% accepted total is intentional. WP16/WP17 acceptance advances Block E implementation but does not credit Block E piecemeal. Block D receives its planned weight only after the deferred WP15 real live broker evidence and the amended Block D acceptance requirements are actually satisfied.
## Accepted implementation evidence index

- WP0 PR #228 -> `7c5de954eed10dd406e743c38f7bdef6b0634108`;
- WP1 PR #229 -> `dbd459b280de84d3f571b458b46f1039880312ca`;
- WP2 PR #230 -> `3e3a89791d7f1594e4e1ba52125f8361708ae29d`;
- WP3 PR #236 -> `289ff563e99a64bbf8b5a289e84668dde58ef42a`;
- WP4 primary PR #248 -> `cc37bdce69331e8b03f5fd46554dc486616414f6`;
- WP4 hardening PR #249 -> `6c97df17f0de21a27ec0d12ee9699d2a00fab53f`; post-merge Regression Shield run `31181814984` — **SUCCESS**;
- WP5 PR #251 -> `d0b80f91a434e93e5facb244a92b17b066ccdf2a`; post-merge Regression Shield run `31252745722` — **SUCCESS**;
- WP6 PR #253 -> `c55fb0a32b309628fb86a7abf9182b95af4beca2`; post-merge Regression Shield run `31270545874` — **SUCCESS**;
- WP7 PR #255 -> `82225eef984f6c14c254108bada0627c1f0368a4`; post-merge Regression Shield run `31281148813` — **SUCCESS**;
- WP8 PR #257 -> `422ef68864050eec858e32d980165c995d9e7ecb`; post-merge Regression Shield run `31284931677` — **SUCCESS**;
- WP9 PR #259 -> `b43da57e74e6c5d4735c2b4e96b6839a52b4d1dc`; post-merge Regression Shield run `31291892741` — **SUCCESS**;
- WP9A PR #261 -> `0e5a7ec750ef3d3c20bb3f01c0f53804017cd938`; post-merge Regression Shield #1445 / run `31294998878` — **SUCCESS**;
- WP10 rebuild PR #267 -> `6ba81af6d8abd676ad994ddef83048c170c99584`; post-merge Regression Shield #1450 / run `31326712297` — **SUCCESS**;
- WP11 clean rebuild PR #269 -> `1aa65e2420a01a5da7b5123a279a5940b3ea59d4`; post-merge Regression Shield #1452 / run `31329587509` — **SUCCESS**;
- WP12 PR #271 -> `365b49ad1ef428f4b534555cf387f2d3504a770f`; post-merge Regression Shield #1454 / run `31332149156` — **SUCCESS**;
- WP13 PR #273 -> `d74b0177c730cad0a8e3a69d1504e226bedbac27`; post-merge Regression Shield #1456 / run `31370195951` — **SUCCESS**;
- WP14 PR #275 -> `ff9bb37b6538fe9665ea0a652a0623354f0195da`; post-merge Regression Shield #1458 / run `31379587986` — **SUCCESS**;
- Identity / Multi-Tenant Account / Authentication planning PR #278 -> `cbf6a7adba78fa56d23e90ce2cfe2952d21a5e5b`; post-merge Regression Shield #1460 — **SUCCESS**;
- WP15 PR #277 -> `f8862d1af88400189d3c0780d2029a87cb5427ca`; post-merge Regression Shield #1461 / run `31419650823` — **SUCCESS**;
- WP16 PR #280 -> `03f3ff2f389b1b683e60e1ccc706cd7f62a9ba35`; post-merge Regression Shield #1463 / run `31468739530` — **SUCCESS**;
- WP17 PR #282 -> `5b6b12f144c9bfa71307dcb28548a97527456b5b`; post-merge WP17 Audit #59 / run `31499348099` — **SUCCESS**; post-merge Regression Shield #1465 / run `31499348098` — **SUCCESS**;
- deferred WP15 live Web support PR #284 -> `791c138429fded8e223f7721e992b5965dd335fd`;
- WP15 OWNER-audit cleanup hardening PR #285 -> `898a85c3550bde871dfdb386ce1240b151ea1573`;
- WP15 localized-Windows Administrators SID hardening PR #286 -> `019e4f0eb4419aa7b935c17e84e401f13ee7bf5c`;
- WP15 PowerShell 5.1 native npm stderr hardening PR #287 -> `bc8c4c528473d17cb49ad3a59bfae8474a254367`; post-merge Regression Shield #1470 / run `31546341698` — **SUCCESS**; WP15 Live Web Support Audit #50 / run `31546341687` — **SUCCESS**; WP16 Audit #147 / run `31546341697` — **SUCCESS**; WP17 Audit #118 / run `31546341658` — **SUCCESS**; WP15 OWNER Audit #4 / run `31546341667` — **OWNER_ACTION_REQUIRED / exit 61**, with independent audit/upload/cleanup succeeding and only the evidence-enforcement step failing as designed;
- WP15 battery-safe Task Scheduler / sanitized startup diagnostics PR #290 -> `bbacbb6ffda591b0aa53f371d435f7f56537b567`; post-merge Regression Shield #1473 / run `31555409157` — **SUCCESS**; WP15 Live Web Support Audit #58 / run `31555409103` — **SUCCESS**; WP16 Audit #157 / run `31555409117` — **SUCCESS**; WP17 Audit #128 / run `31555409163` — **SUCCESS**; WP15 OWNER Audit #6 / run `31555409161` — **OWNER_ACTION_REQUIRED / exit 61**, with exact-head independent audit/upload/cleanup succeeding and only evidence enforcement failing because `evidence_present=false`;
- V10 status synchronization PR #291 -> `876b9ccb55103533ebed4c4ea8efdeb6c4c16ace`;
- WP15 batch-logon startup correction PR #292 -> `00b18df2c7dec106b39a501459ee9462e14bdb84`;
- WP15 canonical OWNER identity bootstrap PR #293 -> `f7119d294d8dc47e94078d07a69f4dd9200a22f1`;
- WP15 OWNER session persistence/readiness hardening PR #294 -> `dbe622ab6ff03a9e7b5655017846f09fea9d085f`;
- WP15 archived session-probe source binding PR #295 -> `5770c38144c4bb55002a54491a500fd511241612`;
- WP15 serialized authenticated Web DB request transactions PR #296 -> `e43409ebbdf8667156d1602a0aa487d6ff53bdfb`;
- WP15 revoked READ connection visibility correction PR #297 -> `0edc5db020dfdaac44cb199c9eca6dd7798f11fc`;
- WP15 immutable broker-account reconnect correction PR #298 -> `bc5842e019ffa5c612b1a0b6cffe00e9c5d2718a`; post-merge Regression Shield #1481 / run `31620202000` — **SUCCESS**; WP15 Live Web Support Audit #106 / run `31620202006` — **SUCCESS**; WP16 Audit #205 / run `31620202052` — **SUCCESS**; WP17 Audit #176 / run `31620202030` — **SUCCESS**; WP15 OWNER Audit #14 / run `31620201999` — **OWNER_ACTION_REQUIRED**, because the real sanitized OWNER evidence is still absent;
- WP15 self-hosted runner fail-safe recovery hardening PR #299 -> `6bd4e2c683386269ee573f25f50cbc8780ac9ff5`; exact-head Self-Hosted Windows CI #874 / run `31627886479` — **SUCCESS**; WP16 #221 / run `31627886484` — **SUCCESS**; WP17 #192 / run `31627886513` — **SUCCESS**; post-merge Regression Shield #1482 / run `31629149440` — **SUCCESS**; WP16 #222 / run `31629149358` — **SUCCESS**; WP17 #193 / run `31629149359` — **SUCCESS**. Hosted Fast PR Checks #782 and Toolchain Compatibility #817 remain billing/spending-limit infrastructure failures and are not credited as PASS.

## WP15 accepted implementation and deferred live evidence

WP15 final reviewed PR head was `077b2dab32f6f0efc281cd18c332bdd80752e4cd`; it was squash-merged as `f8862d1af88400189d3c0780d2029a87cb5427ca` after fresh exact-head authoritative/focused/deferred-live gates and zero blocking review threads. Post-WP15 Regression Shield #1461 / run `31419650823` completed **SUCCESS**.

Accepted WP15 code provides the narrow connection-scoped T-Invest READ layer with `Tenant -> BrokerConnection -> READ credential -> verified broker-account bindings`, fail-closed authority validation, masked outward identity, exact Decimal/UTC normalization, market enrichment and bounded/resumable operations reads. No broker write, transfer/withdrawal, trading-token fallback or Real execution authority was added.

The accepted Identity / Multi-Tenant Account / Authentication Amendment intentionally supersedes the old normal PowerShell OWNER token workflow. The source-controlled marker remains `LIVE_EVIDENCE_STATUS=DEFERRED_TO_WEB_PROVISIONING` until a dedicated reviewed live-acceptance transition records real evidence safely.

The dedicated live support path is now repository-accepted. It provides the temporary loopback-only acceptance runtime, authenticated Web READ-token provisioning, short-lived private parity challenge, sanitized OWNER finalization, guarded cleanup and independent non-admin runner audit. The raw token still enters only through the accepted Web flow and no synthetic evidence may substitute for the real OWNER comparison.

The deferred live gate is still incomplete because the real OWNER evidence does not yet exist. Until that evidence and the independent rerun audit succeed, Block D stays uncredited and WP18 cannot claim real broker data accepted.

## WP15 deferred live support acceptance evidence

The dedicated support implementation was delivered in PR #284 and then hardened only for defects observed during acceptance rehearsal/OWNER execution:

- PR #284 established the acceptance-only loopback Web runtime, temporary Windows runtime/task, PostgreSQL SSPI boundary, short-lived private parity challenge, sanitized pending/final evidence, guarded cleanup and independent runner audit;
- PR #285 corrected the OWNER-audit cleanup shell to a Windows-native path without changing evidence semantics;
- PR #286 replaced localized `Administrators` name lookup with the well-known built-in Administrators SID `S-1-5-32-544` while preserving the non-admin runtime check;
- PR #287 made the three reviewed npm build calls PowerShell-5.1-safe against non-fatal native stderr while keeping `$LASTEXITCODE` authoritative and restoring fail-closed PowerShell error handling immediately afterward;
- PR #290 made the temporary acceptance scheduled task deterministic across laptop battery/AC transitions and, if loopback startup still times out, reports only sanitized Task Scheduler state plus numeric `LastTaskResult` before guarded cleanup so another startup defect can be diagnosed without raw task/Event logs or secret/private data;
- PR #292 added the exact-head acceptance-only starter that temporarily grants only `SeBatchLogonRight` to the validated non-admin runtime SID when required, invokes the reviewed provisioner, and restores the pre-start right state in `finally`;
- PR #293 seeded and verified the canonical OWNER tenant/user during temporary OWNER-admin bootstrap before the least-privilege runtime starts;
- PR #294 made OWNER session persistence/readiness explicit under PostgreSQL transaction boundaries and proved session create/resolve/revoke/cleanup under the actual runtime identity before HTTP serving;
- PR #295 bound the archived session probe to the archived application source root before importing Omni-CIO modules;
- PR #296 serialized complete authenticated Web request transaction contexts on the single acceptance-only local Psycopg connection and added parallel regression coverage;
- PR #297 retained durable revoked BrokerConnection history while excluding revoked rows from the active Settings/live-acceptance listing;
- PR #298 reused the existing immutable broker-account record when the same verified READ account reconnects after revocation, validating immutable identity/hash and stored schema versions fail-closed;
- PR #299 hardened the self-hosted Windows runner diagnostic/recovery path: diagnostics remain read-only/privacy-safe, accepted service identity is bound to the exact runner marker plus exact `RunnerRoot\bin\RunnerService.exe`, recovery is preview-first and permits only bounded start/Automatic mutations after exact revalidation, and actual-node tests require healthy no-op behavior on the authoritative runner.

The latest accepted runtime/operational implementation baseline before this status synchronization is `6bd4e2c683386269ee573f25f50cbc8780ac9ff5`. The product/live Web support contour was last post-merge exercised on immediately preceding `bc5842e019ffa5c612b1a0b6cffe00e9c5d2718a`: Regression Shield #1481 / run `31620202000`, WP15 Live Web Support Audit #106 / run `31620202006`, WP16 #205 / run `31620202052`, and WP17 #176 / run `31620202030` are **SUCCESS**; WP15 OWNER Audit #14 / run `31620201999` reaches the independent evidence-enforcement boundary and remains `OWNER_ACTION_REQUIRED` because the real evidence is absent. PR #299 changed only runner operational support. Its exact reviewed head passed Self-Hosted Windows CI #874 / run `31627886479` with the authoritative merge gate, protected Regression Shield, dependency audit, SAST, secret scan and Windows runner smoke, plus WP16 #221 and WP17 #192. On exact merged `main` `6bd4e2c683386269ee573f25f50cbc8780ac9ff5`, Regression Shield #1482 / run `31629149440`, WP16 #222 / run `31629149358`, and WP17 #193 / run `31629149359` are **SUCCESS**.

This accepted support baseline does not change `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, public ingress, public multi-user activation, broker write/TRADE authority or protected V9 rollback.

## WP16 accepted implementation evidence

WP16 final reviewed PR head was `b4adef760696343382ca7319f7f7ac7e95db671a`; it was squash-merged as `03f3ff2f389b1b683e60e1ccc706cd7f62a9ba35`. Post-WP16 Regression Shield #1463 / run `31468739530` completed **SUCCESS**.

Accepted WP16 provides the single source-controlled Web foundation at `apps/web/` with exact-pinned React/Vite/TypeScript/Node/npm baseline, reusable design tokens/components, responsive/accessibility evidence and dependency/browser security guards. It did not activate WP17 auth/navigation early, public multi-user/ingress, real portfolio UI, broker write, transfer/withdrawal or Real authority.

## WP17 accepted implementation evidence

WP17 final reviewed PR head was:

`bb68126f37270c06763cb1765db5d5944a73bc95`

Fresh exact-head acceptance on that head proved:

- V10 WP13 PostgreSQL Audit #112 / run `31495349542` — **SUCCESS**;
- V10 WP14 Durable Jobs Audit #69 / run `31495349554` — **SUCCESS**;
- V10 WP15 T-Invest Read Audit #137 / run `31495349539` — **SUCCESS**;
- V10 WP16 Web Design System Audit #87 / run `31495349584` — **SUCCESS**;
- V10 WP17 Application Shell Audit #58 / run `31495349557` — **SUCCESS**;
- Self-Hosted Windows CI #757 / run `31495349537` — **SUCCESS**, including protected Regression Shield with coverage, dependency audit, SAST and tracked-content secret scan;
- V10 WP17 OWNER Read Vault Audit #12, rerun attempt 2 — **SUCCESS**, exact implementation/script hashes bound, runner non-admin, runner secret read/write denied, runner evidence write denied, no real secret values used, `ready=true`;
- review submissions — **zero**;
- blocking inline review threads — **zero**;
- PR conversation comments — **zero**;
- base `main...head` was `behind_by=0` with exactly 44 expected files.

GitHub-hosted Fast PR Checks #665 and Toolchain Compatibility #700 did not start because GitHub reported account payment/spending-limit startup failure. They remain recorded as external hosted-infrastructure/billing failures, **not PASS and not code failures**; downstream skipped jobs are not credited.

PR #282 was squash-merged with an exact-head guard as:

`5b6b12f144c9bfa71307dcb28548a97527456b5b`

That exact commit became `main`. Post-merge WP17 Application Shell Audit #59 / run `31499348099` completed **SUCCESS**. Mandatory post-merge Regression Shield #1465 / run `31499348098` also completed **SUCCESS**: its quality/contracts/coverage job passed dependency-lock reproduction, policy/repository/toolchain/regression guards, compile, Ruff, formatter baseline, mypy, stable gateway entrypoint, read-only release contract and the full Regression Shield with coverage; its independent security job passed runtime dependency audit, medium/high-confidence SAST and tracked-content secret scan.

### WP17 functional/security acceptance

Accepted WP17 provides:

- the single source-controlled authenticated application shell and canonical navigation routes;
- Telegram/VK ID provider abstraction while real provider credentials/public ingress remain disabled;
- server-side opaque revocable sessions with no browser Web Storage credential/session state;
- server-derived tenant context and route guards;
- global health/freshness and degraded-state behavior;
- Web build/version identity shown only on System;
- authenticated `Settings -> Broker Connections` READ-token preview/select/commit/replace/revoke UX;
- accepted WP15 multi-account READ validation reused rather than replaced;
- connection-scoped WP8 DPAPI LocalMachine READ vault child with no `broker_trading` authority;
- PostgreSQL session/BrokerConnection/account-binding metadata without raw token/ciphertext storage;
- exact-head OWNER ACL/evidence finalization and an independent non-admin negative probe;
- local/private acceptance only: public registration, public multi-user activation and public Internet ingress remain OFF/LOCKED.

WP17 did not add a T-Invest TRADE credential, order/withdrawal API, broker write authority, WP18 real portfolio UI or Real execution activation. Protected `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and V9 rollback remain unchanged.

## Next required gate — deferred WP15 real live broker READ acceptance

The accepted amendment states that WP18 Portfolio Dashboard may consume real broker data only after Web READ-token provisioning completes the deferred WP15 live evidence for the corresponding tenant/broker account.

The smallest dedicated live-acceptance support path has now been implemented, hardened and accepted. No further WP18 feature work is authorized before the real evidence gate.

The remaining sequence is deliberately physical and evidence-bound:

1. OWNER starts the temporary acceptance runtime from the exact accepted implementation using the reviewed runbook; if a previous attempt partially provisioned the owned runtime, run the marker-guarded cleanup first;
2. OWNER enters the real T-Invest READ-only token only through the loopback authenticated Web `Settings -> Broker Connections` flow;
3. OWNER locally verifies intended masked account, portfolio-summary parity, one deterministic sample-position quantity/value parity and freshness, then confirms only true booleans;
4. OWNER runs the reviewed finalizer, which writes only sanitized evidence and automatically removes the temporary acceptance runtime;
5. engineering reruns the independent non-admin `V10 WP15 Live Web OWNER Audit` on the same exact implementation SHA;
6. only after that audit is GREEN may a separate acceptance/status transition credit Block D and evaluate WP18 unlock.

No synthetic evidence may replace step 3. The real token itself must never be sent in chat, PowerShell command history, GitHub, CI logs or artifacts.

Until the real live evidence passes and its own acceptance/status transition is merged and post-merge regression-verified:

- Block D credit remains withheld;
- WP18 real-data acceptance remains locked;
- WP18 feature work remains locked by this status;
- public multi-user remains OFF;
- public Internet ingress remains OFF;
- broker write / TRADE / Real authority remains unchanged.

## Permanent safety / rollback invariants

The following remain mandatory while V10 develops:

- deployment entrypoint: `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker write authority is not expanded by planning, Web or read-adapter work;
- no real broker/Telegram/VK tokens, encryption/recovery keys, private portfolio payload or full account IDs in GitHub, CI logs or artifacts;
- protected V9 rollback remains preserved;
- red CI is red; skipped is not PASS; billing/infrastructure failure is distinct from code failure;
- every feature/acceptance package uses its own branch and PR;
- mandatory CI, exact-head review, zero unresolved blocking threads, squash merge and post-merge Regression Shield remain required before formal acceptance;
- OWNER physical/secret evidence is never synthesized.

## Current next action

Perform the non-delegable OWNER local/private deferred-WP15 live acceptance on the exact accepted `main` using `docs/operations/V10_WP15_OWNER_LIVE_READ_RUNBOOK.md`. If a previous attempt created any partial owned WP15 runtime state, run the reviewed marker-guarded `-Cleanup` path first. Enter the real T-Invest READ token only in the loopback authenticated Web `Settings -> Broker Connections` form; never in PowerShell, chat, GitHub, CI logs or artifacts. After sanitized OWNER finalization, rerun the independent non-admin `V10 WP15 Live Web OWNER Audit` on the same exact implementation SHA. WP18 remains locked until that audit is GREEN.