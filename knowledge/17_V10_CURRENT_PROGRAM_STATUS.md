# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-10

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / BLOCK C COMPLETE / WP13 COMPLETE / BLOCK D IN PROGRESS / WP14 NEXT**.

Accepted implementation progress remains **26%**. Block C's full 12% weight is accepted. Block D is not credited yet: WP11–WP13 are accepted, while WP14–WP15 and the Block D Exit Gate remain.

Accepted completed work:

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
- GitHub Pro hybrid CI / Lenovo continuity hardening — **COMPLETE infrastructure hardening**;
- V10 release/build provenance, protected `v10.*` tag identity, immutable-release operating contract and fail-closed deployment provenance — **COMPLETE**;
- accepted V10 planning amendments remain binding but do not credit later runtime implementation before their owning WPs pass.

Current authorized implementation work package is now:

**WP14 — Durable Job System.**

WP14 may implement the runtime semantics for durable background work on top of the accepted WP13 PostgreSQL `jobs` persistence shape: explicit job identity/type/idempotency key/state, lease ownership/expiry, bounded attempts/retry timing, correlation identity and sanitized failure classification. It may add worker/scheduler/recovery code only to the extent required for durable jobs.

WP14 must prove crash-mid-job recovery, duplicate scheduling/idempotency, lease-expiry/concurrency safety, bounded retries and reboot behavior. Incomplete work after restart must either resume safely or be marked for explicit reconciliation rather than being silently lost or blindly replayed.

WP14 does **not** authorize starting WP15 T-Invest read integration early, enabling Web/Telegram/Cortex/public multi-user surfaces, changing broker/Real-money authority, weakening WP6–WP13 privilege/secret/recovery/Core/domain/persistence boundaries, changing `app:app`, or changing accepted financial semantics without explicit proof.

Owner start command: **`START V10`** received 2026-08-05.

Starting or advancing V10 never expands broker/Real-money authority by itself.

## Canonical authority

Base program:

- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`;
- `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`.

Accepted planning elaborations are indexed by `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`. Binding execution/navigation sources additionally include:

- `AGENTS.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` for protected V9 runtime state;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `docs/master-plan/OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_GITHUB_PRO_AND_MIGRATION_IMPLEMENTATION_AMENDMENT.md`;
- accepted architecture/security/recovery contracts under `docs/architecture/` and `docs/operations/`.

Protected production/recovery baseline remains **Omni-CIO v9.0.0 — COMPLETE / owner-accepted / controlled maintenance** until the responsible later V10 parity/decommission gate.

## Progress

| Block | Planned weight | Accepted state |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | COMPLETE — WP1 / WP2 / WP3 / WP4 |
| C. Lenovo Omni-CIO Node / infrastructure | 12% | COMPLETE — WP5 / WP6 / WP7 / WP8 / WP9 / WP9A / WP10 |
| D. V10 Core and data | 14% | IN PROGRESS — WP11 / WP12 / WP13 COMPLETE / WP14 NEXT |
| E. Omni-CIO Web Platform | 14% | NOT STARTED |
| F. Telegram | 8% | NOT STARTED — product/interaction contract pre-approved only |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED — autonomous portfolio-governance role pre-approved only |
| I. Personal Real Execution | 7% | NOT STARTED — cash-only confirmed execution policy pre-approved only |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED — commercial/license/update/legal-gate planning pre-approved only |
| **TOTAL** | **100% planned** | **26% ACCEPTED** |

Block B's full 9% weight is accepted because WP4 and the Block B Exit Gate are complete. Block C's full 12% weight is accepted because WP5–WP10 are complete and practical encrypted off-device recovery, replacement-node recovery procedure, privilege separation, secret isolation, supervision/operations boundaries and post-merge regression/security evidence satisfy the Block C infrastructure/recovery gate. Block D remains uncredited until WP14–WP15 and its Exit Gate complete.

## Accepted implementation evidence

- WP0 PR #228 -> `7c5de954eed10dd406e743c38f7bdef6b0634108`;
- WP1 PR #229 -> `dbd459b280de84d3f571b458b46f1039880312ca`;
- WP2 PR #230 -> `3e3a89791d7f1594e4e1ba52125f8361708ae29d`;
- WP3 PR #236 -> `289ff563e99a64bbf8b5a289e84668dde58ef42a`;
- WP4 primary PR #248 -> `cc37bdce69331e8b03f5fd46554dc486616414f6`;
- WP4 artifact-transport hardening PR #249 -> `6c97df17f0de21a27ec0d12ee9699d2a00fab53f`; post-merge Regression Shield run `31181814984` — **SUCCESS**;
- WP5 PR #251 -> `d0b80f91a434e93e5facb244a92b17b066ccdf2a`; post-merge Regression Shield run `31252745722` — **SUCCESS**;
- WP6 PR #253 -> `c55fb0a32b309628fb86a7abf9182b95af4beca2`; post-merge Regression Shield run `31270545874` — **SUCCESS**;
- WP7 PR #255 -> `82225eef984f6c14c254108bada0627c1f0368a4`; exact-head Windows/Lenovo gates passed and post-merge Regression Shield run `31281148813` — **SUCCESS**;
- WP8 PR #257 -> `422ef68864050eec858e32d980165c995d9e7ecb`; exact-head secret-store/Windows/Lenovo gates passed and post-merge Regression Shield run `31284931677` — **SUCCESS**;
- WP9 PR #259 -> `b43da57e74e6c5d4735c2b4e96b6839a52b4d1dc`; post-merge Regression Shield run `31291892741` — **SUCCESS**;
- WP9A PR #261 -> `0e5a7ec750ef3d3c20bb3f01c0f53804017cd938`; post-merge Regression Shield #1445 / run `31294998878` — **SUCCESS**;
- WP10 rebuild PR #267 -> `6ba81af6d8abd676ad994ddef83048c170c99584`; post-merge Regression Shield #1450 / run `31326712297` — **SUCCESS**;
- WP11 clean rebuild PR #269 -> `1aa65e2420a01a5da7b5123a279a5940b3ea59d4`; post-merge Regression Shield #1452 / run `31329587509` — **SUCCESS**;
- WP12 PR #271 -> `365b49ad1ef428f4b534555cf387f2d3504a770f`; post-merge Regression Shield #1454 / run `31332149156` — **SUCCESS**;
- WP13 PR #273 -> `d74b0177c730cad0a8e3a69d1504e226bedbac27`; post-merge Regression Shield #1456 / run `31370195951` — **SUCCESS**.

### WP10 accepted evidence

WP10 implementation exact head `53b2d82e1a813144ce2fc104aa4ea46f01ac8d11` passed the fresh ready-for-review gates before squash merge:

- authoritative Self-Hosted Windows CI #526 / run `31326111726` — **SUCCESS**;
- V10 WP10 Recovery Audit #139 / run `31326111735` — **SUCCESS**;
- V10 WP10 OWNER Physical Audit #31 / run `31326111749` — **SUCCESS**;
- inline PR review threads — **zero**.

The accepted WP10 recovery design sets RPO **60 minutes** after product DB binding and RTO **240 minutes**, implements PostgreSQL 18 custom-format backup/restore with SHA-256 and exact-size integrity evidence, atomic local/off-device promotion, corrupt-backup rejection, bounded retention of up to 72 verified bundles / 30 days, explicit allowlist-only private non-secret metadata backup, and separate recovery paths for GitHub engineering source, encrypted private durable state and runtime secrets.

The OWNER physical rehearsal used a reviewed existing non-system BitLocker Data volume without formatting/repartitioning. Sanitized evidence proved the target was fully encrypted with protection on, recovery-key custody was separately confirmed without recording the key, the off-device bundle was copied and re-verified, a deliberately corrupted copy was rejected, a valid off-device copy restored into a separate PostgreSQL database with exact probe parity, temporary synthetic state was cleaned, and the non-admin runner was denied both read and write access to the backup payload. The final ready-for-review OWNER audit retained only sanitized evidence; no recovery key value, raw disk identity, private portfolio payload, account identifier, secret value or private DB archive was collected by CI.

The implementation was squash-merged as `6ba81af6d8abd676ad994ddef83048c170c99584`. Post-WP10 Regression Shield #1450 / run `31326712297` on that exact `main` SHA completed **SUCCESS**: quality/contracts/coverage, dependency audit, SAST and tracked-content secret scan all passed.

GitHub-hosted `V10 Fast PR Checks` and `V10 Toolchain Compatibility` jobs on the WP10 exact head did not start because GitHub reported account payment/spending-limit startup failure. They are recorded as external hosted-infrastructure/billing failures, not as PASS and not as code failures. The authoritative Lenovo merge gate and WP10-specific recovery/OWNER gates were GREEN on the exact reviewed head.

### WP11 accepted evidence

WP11 was rebuilt on the accepted post-WP10 baseline rather than using the earlier rejected premature WP11 branch. Final implementation exact head `8a05b85f94112ffec296b06377f3834e820f45fa` passed authoritative Self-Hosted Windows CI #529 / run `31329239414` — **SUCCESS**. Its authoritative merge gate completed repository/CI policy checks, compilation, Ruff/mypy/static quality, stable gateway/read-only release checks, the full Regression Shield with coverage, dependency audit, SAST and tracked-content secret scan successfully. Inline review threads were **zero**.

The accepted WP11 implementation inventories the V9 WP1–WP14 engine/source boundaries, preserves `app:app`, and adds a narrow `omni_cio/core` planning facade using the existing reviewed policy/risk/strategy/optimizer/plan engines rather than rewriting financial semantics. `CorePlanRequestV1` and `CorePlanResultV1` compose accepted V9 versioned DTOs; explicit evaluation time makes deterministic replay independent of the presentation layer.

The golden parity test executes the new no-GPT Core facade from the existing `tests/v9_plan_fixture.py` inputs and requires exact typed equality for policy assessment, portfolio risk, meta-strategy, optimizer and immutable plan. A second replay must be identical. Static import-boundary tests reject dependencies on `app*`, `gpt`, OpenAI, `omni_cio.real_trading` and `omni_cio.plan_execution` from the direct deterministic planning path. `trading_methods=false` remains asserted.

GitHub-hosted `V10 Fast PR Checks` and `V10 Toolchain Compatibility` on the final WP11 exact head did not start because GitHub again reported the account payment/spending-limit startup failure. They are recorded as external hosted-infrastructure/billing failures, not as PASS and not as code failures. The exact-head authoritative Lenovo gate was GREEN.

WP11 was squash-merged as `1aa65e2420a01a5da7b5123a279a5940b3ea59d4`. Post-WP11 Regression Shield #1452 / run `31329587509` on that exact `main` SHA completed **SUCCESS**, including quality/contracts/coverage, dependency audit, SAST and tracked-content secret scan.

### WP12 accepted evidence

WP12 final implementation exact head `0d933154901c10d07e82d12dbed47e0ef69cd8cc` passed authoritative Self-Hosted Windows CI #532 / run `31331627139` — **SUCCESS**. The authoritative merge gate completed repository/CI policy checks, compilation, static quality, the full Regression Shield with coverage, dependency audit, SAST and tracked-content secret scan successfully; Windows runner smoke was also **SUCCESS**. Inline review threads were **zero**.

The accepted WP12 model adds strict immutable/versioned canonical identities and explicit OWNER tenant/portfolio/policy scope for Tenant, User, BrokerAccount, Portfolio, PortfolioSnapshot, Position, Instrument, Policy, Evidence, Incident, Decision, Plan, Execution and Journal records without starting persistence. OWNER is the only admitted tenant/user in Personal V10; cross-tenant access fails closed. Broker accounts use internal canonical IDs plus masked labels and SHA-256 fingerprints rather than raw full account identifiers. Instruments require strong broker UID/FIGI/ISIN identity, keep ticker/name as secondary display/board aliases and reject conflicting alias collisions. Persisted timestamps are timezone-aware and normalized to UTC while evidence/snapshot contracts preserve distinct published/retrieved/broker-server/local-receive meanings.

WP12 records the canonical-domain decision as `WRAP_ADAPTER`: accepted V9 financial payload contracts remain the financial-semantics authority while the new V10 domain layer adds identity/scope envelopes and validation. Tests cover strict schemas, OWNER-only admission, account masking, strong instrument identity, display-label stability, alias and duplicate-position collision rejection, missing-reference/cross-portfolio scope rejection, UTC normalization and an explicit no-persistence/no-execution-authority boundary.

The first WP12 exact-head authoritative run exposed a real Ruff `F841` code failure. It was not called PASS; the unused binding and adjacent static-typing weaknesses were corrected at root cause, producing the final exact head above. GitHub-hosted `V10 Fast PR Checks` and `V10 Toolchain Compatibility` on that final head did not start because GitHub reported the account payment/spending-limit startup failure. They are recorded as external hosted-infrastructure/billing failures, not as PASS and not as code failures.

WP12 was squash-merged as `365b49ad1ef428f4b534555cf387f2d3504a770f`. Post-WP12 Regression Shield #1454 / run `31332149156` on that exact `main` SHA completed **SUCCESS**, including quality/contracts/coverage, dependency audit, SAST and tracked-content secret scan.

### WP13 accepted evidence

WP13 final implementation exact head `a6ae5d2eba2e8819aa67724844eee6e7845277e5` passed the fresh ready-for-review exact-head gates:

- `V10 WP13 PostgreSQL Audit` #43 / run `31369431710` — **SUCCESS**;
- authoritative Self-Hosted Windows CI #576 / run `31369431818` — **SUCCESS**;
- inline review threads and PR comments — **zero**.

The accepted WP13 implementation adds one PostgreSQL 18 schema family `omni_cio_v10` with immutable ordered SHA-256-verified migrations, a transaction-scoped advisory migration lock, OWNER-scoped WP12 referential integrity, Decimal-backed `numeric(38,18)` quantity storage, timezone-aware `timestamptz`, append-only protection for audit-sensitive relations, idempotent immutable replay with conflict rejection, deterministic state revisions/digests, bounded research/health retention and content-addressed private durable payload storage. The `jobs` relation remains persistence shape only; WP14 owns runtime job semantics.

The focused PostgreSQL acceptance rehearsal proved zero-to-current migration, migration-race serialization, exact Decimal round-trip, OWNER/cross-scope enforcement, append-only mutation rejection, concurrent identical replay convergence, conflicting replay rejection, bounded cache retention, WP10 logical backup integrity, intentional corrupt-backup rejection, restore into a separate PostgreSQL database and exact migration/state digest parity. It used only synthetic state and emitted sanitized short-retention evidence.

The authoritative Lenovo gate passed lock verification, repository/CI policy contracts, compilation, Ruff/format/mypy, stable `app:app`, read-only GPT Actions contract, full Regression Shield with coverage, dependency audit, SAST and tracked-content secret scan. GitHub-hosted `V10 Fast PR Checks` and `V10 Toolchain Compatibility` did not start because GitHub reported account payment/spending-limit startup failure; they remain recorded as external hosted-infrastructure failures, not PASS and not code failures.

WP13 was squash-merged as `d74b0177c730cad0a8e3a69d1504e226bedbac27`. Post-WP13 Regression Shield #1456 / run `31370195951` on that exact `main` SHA completed **SUCCESS**, including quality/contracts/coverage, dependency audit, SAST and tracked-content secret scan.

## Accepted engineering and product locks

The following remain binding while later WPs are implemented:

- V10 is controlled migration/productization of accepted V9, not a greenfield rewrite; default decision preference is `REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`;
- deterministic Core owns financial/accounting truth and money-path enforcement; AI never replaces deterministic calculations or receives direct broker-write authority;
- verified broker HTML account report import is the V10 accounting target; screenshot/OCR portfolio ingestion is not the target;
- MOEX current-market enrichment remains distinct from broker period-end accounting truth;
- local-first Cortex baseline remains Qwen3.5-4B via replaceable Ollama provider, but runtime installation/activation follows its owning later WP;
- research/evidence must carry provenance/freshness/identity binding and retrieved external text is untrusted data;
- GitHub is engineering Control Plane, not secret/private-portfolio custody and never broker authority;
- Lenovo is the first replaceable Personal runtime node and the authoritative heavy Windows/continuity lane;
- Telegram remains a later OWNER-only companion to the same Core/Web/Cortex and owns no financial calculation or broker-write authority;
- Real READ, Sandbox and Real TRADING credentials remain isolated; transfer/withdrawal, margin/short and autonomous Real execution remain forbidden;
- `REAL_TRADING_ENABLED=false` remains the master Real rollback until a responsible later package explicitly changes and proves the boundary.

## Current authorized next step — WP14

WP14 is now the only authorized implementation package after accepted WP13 and successful post-WP13 Regression Shield.

WP14 goal: make background work observable, idempotent and recoverable after restart using the accepted WP13 PostgreSQL persistence boundary rather than introducing a second queue/database stack.

WP14 must cover at minimum:

- durable job identity with type, idempotency key, state, lease, attempts, next-run time, sanitized error class and correlation identity;
- bounded scheduling/claim/lease/heartbeat/completion/failure transitions with database-enforced concurrency safety;
- bounded retry classification so permanent/validation errors do not loop forever;
- crash-mid-job and lease-expiry recovery semantics;
- duplicate scheduling/idempotency behavior;
- a durable job journal/history sufficient to explain what actually ran;
- safe reboot behavior where unfinished work either resumes correctly or is explicitly marked for reconciliation;
- persistence/recovery integration without weakening WP10/WP13 backup/restore guarantees.

WP14 must preserve all accepted WP6–WP13 privilege, secret, supervision, operations, recovery, deterministic-Core, canonical-domain and PostgreSQL boundaries. It must not start WP15 broker-read integration early, activate Web/Telegram/Cortex/public multi-user surfaces, expose private state/secrets, weaken CI, or expand broker-write/Real-money authority.

Only after WP14 Exit Gate passes may WP15 begin.

## Money/safety rule

GitHub access, AI output, research result, Watchtower alert, Telegram message/button, `START V10`, development approval, update availability, backup availability, database/job availability or model output is never broker-submit authorization.

Current V9 money-path invariants, `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, secret separation and kill switches remain binding until an explicitly responsible later V10 work package replaces a boundary and passes its Exit Gate.