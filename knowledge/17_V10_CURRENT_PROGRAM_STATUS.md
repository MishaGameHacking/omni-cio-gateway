# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-11

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / BLOCK C COMPLETE / WP15 CODE+SECURITY ACCEPTED / BLOCK D LIVE ACCEPTANCE DEFERRED / WP16 COMPLETE / WP17 NEXT**.

Accepted implementation progress remains **26%**.

Block C's full 12% weight is accepted. Block D is deliberately **not credited** yet: WP11–WP14 are complete and WP15 implementation/code/security is accepted, but the OWNER-approved Identity / Multi-Tenant Account / Authentication Amendment defers the real T-Invest live acceptance to the authenticated Web broker-provisioning flow owned by WP17. WP18 real-data acceptance remains locked until that deferred evidence passes.

WP16 is now accepted through its implementation merge and exact-main post-merge Regression Shield. Block E remains in progress and is not credited piecemeal before its own Block Exit Gate.

The next authorized implementation work package is:

**WP17 — Application Shell and navigation.**

WP17 owns the stable authenticated account shell, navigation, Telegram/VK identity-provider abstraction, server-side session semantics, route guards, API error boundary, global health/freshness indicator and the authenticated `Settings -> Broker Connections` product flow required by the accepted Identity / Multi-Tenant Account / Authentication Amendment.

WP17 may exercise OWNER/test identities before public launch, but public registration and public multi-user activation remain disabled until their later external-ingress, isolation, security, legal and commercial gates pass. Public Internet ingress remains OFF. Starting WP17 does not itself credit Block D or unlock WP18 real broker-data acceptance.

Owner action required now: **none**.

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
- Block D / WP15 — **IMPLEMENTATION / CODE / SECURITY ACCEPTED; LIVE BROKER EVIDENCE DEFERRED TO WP17**;
- Block E / WP16 — **COMPLETE**;
- Block E / WP17 — **NEXT / AUTHORIZED after this status transition is itself merged and regression-verified**;
- Block E / WP18+ — **LOCKED behind WP17 Exit Gate and owning dependencies**;
- WP18 real-data acceptance — **LOCKED behind deferred WP15 live evidence**;
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

The current WP15/WP16/WP17 sequencing is additionally governed by the accepted OWNER amendment:

- `docs/master-plan/OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md`;
- `docs/architecture/ADR-0010-identity-multitenant-authentication.md`;
- `docs/architecture/V10_IDENTITY_AUTHENTICATION_CONTRACT.json`;
- `docs/operations/V10_IDENTITY_AND_BROKER_CONNECTION_SECURITY_NOTES.md`;
- `docs/architecture/V10_WP15_TINVEST_READONLY_CONTRACT.md`;
- `docs/architecture/V10_WP15_LIVE_ACCEPTANCE_STATE.json`;
- `docs/architecture/V10_WP16_WEB_DESIGN_SYSTEM_CONTRACT.md`.

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
| D. V10 Core and data | 14% | IMPLEMENTATION ACCEPTED THROUGH WP15 CODE+SECURITY; LIVE BROKER EVIDENCE DEFERRED / BLOCK CREDIT WITHHELD |
| E. Omni-CIO Web Platform | 14% | IN PROGRESS — WP16 COMPLETE / WP17 NEXT |
| F. Telegram | 8% | NOT STARTED — product/interaction contract pre-approved only |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED — autonomous portfolio-governance role pre-approved only |
| I. Personal Real Execution | 7% | NOT STARTED — cash-only confirmed execution policy pre-approved only |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED — commercial/license/update/legal-gate planning pre-approved only |
| **TOTAL** | **100% planned** | **26% ACCEPTED** |

The 26% accepted total is intentional. WP16 acceptance advances Block E implementation but does not credit Block E piecemeal. Block D receives its planned weight only after the deferred WP15 live broker evidence and the amended Block D acceptance requirements are actually satisfied.

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
- WP16 PR #280 -> `03f3ff2f389b1b683e60e1ccc706cd7f62a9ba35`; post-merge Regression Shield #1463 / run `31468739530` — **SUCCESS**.

## WP15 accepted implementation evidence

WP15 final reviewed PR head was:

`077b2dab32f6f0efc281cd18c332bdd80752e4cd`

The mandatory fresh `ready_for_review` exact-head cycle passed:

- authoritative Self-Hosted Windows CI #671 / run `31418366667` — **SUCCESS**;
- V10 WP15 T-Invest Read Audit #79 / run `31418367931` — **SUCCESS**;
- V10 WP15 Deferred Live Audit #69 / run `31418366669` — **SUCCESS**;
- review submissions — **zero**;
- blocking inline review threads — **zero**;
- `main...head` was `behind_by=0` with exactly 22 expected WP15 files.

The authoritative final gate passed lock verification, repository/security policy, compile, Ruff, formatting, mypy, stable `app:app`, read-only release contract, full Regression Shield with coverage, dependency audit, SAST and tracked-content secret scan. WP5-only physical-evidence steps were unrelated/skipped and were not counted as WP15 PASS evidence. Failure-diagnostic upload was skipped because no failure occurred and was not counted as PASS evidence.

The focused WP15 gate passed deterministic static quality, unit/authority tests and offline rehearsal. The deferred-live gate proved the ordinary CI runner cannot read the private broker credential/binding boundaries and that the source-controlled deferral marker is exact.

GitHub-hosted Fast PR Checks #579 / run `31418366644` and Toolchain Compatibility #614 / run `31418366536` did not start because GitHub reported account payment/spending-limit startup failure. They remain recorded as external hosted-infrastructure/billing failures, **not PASS and not code failures**.

PR #277 was squash-merged with an exact-head guard as:

`f8862d1af88400189d3c0780d2029a87cb5427ca`

Post-WP15 Regression Shield #1461 / run `31419650823` ran on that exact `main` SHA and completed **SUCCESS**. Its quality/contracts/coverage job passed lock, policy, repository boundaries, compile, lint, format, type checking, stable entrypoint, read-only release and full regression coverage. Its independent security job passed dependency audit, medium/high-confidence SAST and tracked-content secret scan.

### WP15 functional/security acceptance

Accepted WP15 code provides a narrow connection-scoped T-Invest READ layer with:

- `Tenant -> BrokerConnection -> READ credential -> verified broker-account bindings` semantics for the owning future authenticated server context;
- broad or narrow READ-token account discovery;
- masked outward broker identity and exact expected-account fingerprint binding;
- fail-closed rejection of duplicate identity, absent expected binding and any account authority broader/unknown than `READ_ONLY`, except explicit `NO_ACCESS`;
- rejection of broader/unknown authority even on a closed account record as defense-in-depth;
- a production SDK proxy with an explicit READ allowlist and no Orders/StopOrders/Users-write/raw delegate escape;
- exact Decimal/UTC normalization, freshness/completeness markers, blocked-position semantics and strong instrument identity validation;
- current market-price enrichment;
- bounded/resumable operations cursor reads with explicit resume cursor, semantic dedupe, retry/backoff/jitter and conservative rate-limit-aware pacing;
- reuse of accepted WP12 canonical contracts, WP13 PostgreSQL boundaries and WP14 durable-job semantics without a competing persistence/queue stack;
- preservation of the WP8 protected-secret compatibility boundary.

No broker-write, transfer/withdrawal, trading-token fallback or Real execution authority was added.

### Deferred live acceptance

The accepted Identity / Multi-Tenant Account / Authentication Amendment intentionally supersedes the old normal PowerShell OWNER token workflow.

Current source-controlled state remains:

- `LIVE_EVIDENCE_STATUS=DEFERRED_TO_WEB_PROVISIONING`;
- normal broker provisioning surface = authenticated WP17 Web Settings;
- real broker token required now = **false**;
- Block D credit allowed now = **false**;
- WP18 real-data acceptance = **locked**;
- public multi-user enabled = **false**;
- broker-write authority added = **false**;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`.

No real T-Invest token, full broker account ID, private portfolio payload or real broker-data acceptance evidence was requested for WP15 code/security acceptance.

The deferred live gate must later be completed through the reviewed WP17 authenticated Web flow. For the authenticated tenant/BrokerConnection it must prove READ_ONLY authority, intended broker-account selection, portfolio-summary parity, one sample-position quantity/value parity, acceptable freshness and sanitized evidence bound to the reviewed implementation. Until then Block D stays uncredited and WP18 cannot claim real broker data accepted.

## WP16 accepted implementation evidence

WP16 final reviewed PR head was:

`b4adef760696343382ca7319f7f7ac7e95db671a`

The mandatory fresh `ready_for_review` exact-head cycle passed:

- authoritative Self-Hosted Windows CI #698 / run `31468182852` — **SUCCESS**;
- V10 WP16 Web Design System Audit #26 / run `31468182877` — **SUCCESS**;
- synthetic visual/lock evidence artifact `9092305754`, digest `sha256:f367dc9613d3a9cbd9a11cbc52aa28b70c2ee14af38aacc1fe3e2a2e422772a1`;
- review submissions — **zero**;
- blocking inline review threads — **zero**;
- PR conversation comments — **zero**;
- `main...head` was `behind_by=0` with exactly 23 expected WP16 files.

The focused Web gate proved exact-head checkout, exact Node 24.18.0/npm 11.16.0 identity, committed package-lock v3 reproducibility, `npm ci`, strict TypeScript typecheck, Web lint contract, deterministic unit contracts, Vite production build, Playwright browser accessibility/keyboard/reduced-motion checks, 360/768/1440 responsive screenshot evidence, npm dependency audit, permanent Web/repository contracts and clean Lenovo workspace.

The authoritative final gate passed lock verification, repository/security policy, compile, Ruff, formatting, mypy, stable `app:app`, read-only release contract, full Regression Shield with coverage, dependency audit, SAST and tracked-content secret scan. WP5-only physical-evidence steps were unrelated/skipped and were not counted as WP16 PASS evidence. Failure-diagnostic upload was skipped because there was no failure and was not counted as PASS evidence.

GitHub-hosted Fast PR Checks #606 / run `31468182864` and Toolchain Compatibility #641 / run `31468182801` did not start because GitHub reported account payment/spending-limit startup failure. They remain recorded as external hosted-infrastructure/billing failures, **not PASS and not code failures**.

PR #280 was squash-merged with an exact-head guard as:

`03f3ff2f389b1b683e60e1ccc706cd7f62a9ba35`

Post-WP16 Regression Shield #1463 / run `31468739530` ran on that exact `main` SHA and completed **SUCCESS**. Its independent security job passed dependency audit, medium/high-confidence SAST and tracked-content secret scan. Its quality/contracts/coverage job passed lock/policy/repository/toolchain contracts, compile, Ruff, formatting, mypy, stable `app:app`, read-only release contract and the full protected Regression Shield with coverage.

### WP16 functional/security acceptance

Accepted WP16 provides the single source-controlled Web foundation at `apps/web/` with:

- exact-pinned React/Vite/TypeScript/Node/npm baseline and reproducible package-lock v3;
- semantic typography/spacing/surface/focus/operational-state/risk tokens for light and dark themes;
- reusable cards, buttons, badges, fields, tables, chart wrapper, dialog/drawer, toast, skeleton and feedback-state primitives;
- canonical operational/risk vocabulary instead of Web-specific financial meanings;
- mobile-first 360/768/1440 responsive layout evidence;
- keyboard/focus/accessibility-label smoke and reduced-motion handling;
- browser and dependency/security guards that fail closed on unsupported drift;
- synthetic visual evidence only; no broker credential or private portfolio data.

WP16 did **not** introduce WP17 navigation/auth/session/broker-provisioning flows, public multi-user activation, public ingress, WP18 real portfolio UI, Cortex/Telegram runtime, broker write, transfer/withdrawal or Real authority.

## WP17 authorization and scope guard

WP17 — **Application Shell and navigation** — becomes the only authorized feature work package after this status-only transition is merged and its post-status Regression Shield succeeds.

WP17 must build on the accepted WP16 design system rather than invent local visual patterns. It owns:

- stable application navigation and route structure from the Master Plan;
- authenticated Omni-CIO account shell;
- Telegram and VK ID provider abstraction under the accepted identity amendment;
- revocable server-side session semantics, logout/switch/revoke controls and route guards;
- API error boundary and global health/freshness indication;
- system-page non-secret Web build version/Git SHA;
- authenticated `Settings -> Broker Connections` normal provisioning/replacement/revocation flow for tenant-owned broker credentials;
- the reviewed path that will later obtain the deferred WP15 live READ evidence without returning/storing raw credentials in browser storage.

WP17 must **not** activate public multi-user registration, expose public Internet ingress, centralize private portfolio/broker secrets, implement WP18 real portfolio UI early, add a second Web/Core/persistence stack, expand broker write authority or enable Real execution.

The deferred WP15 live broker evidence remains a separate real-data acceptance condition. Until it passes, Block D remains uncredited and WP18 cannot claim real broker-data acceptance.

## Permanent safety / rollback invariants

The following remain mandatory while V10 develops:

- deployment entrypoint: `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker write authority is not expanded by planning, Web or read-adapter work;
- no real broker/Telegram/VK tokens, encryption/recovery keys, private portfolio payload or full account IDs in GitHub, CI logs or artifacts;
- protected V9 rollback remains preserved;
- red CI is red; skipped is not PASS; billing/infrastructure failure is distinct from code failure;
- every feature WP uses its own branch and PR;
- mandatory CI, exact-head review, zero unresolved blocking threads, squash merge and post-merge Regression Shield remain required before formal acceptance;
- OWNER physical/secret evidence is never synthesized.

## Current next action

Complete this WP16 status-only acceptance through PR/CI/post-merge Regression Shield. Only after that exact status merge is GREEN may the WP17 feature branch be opened.