# Архитектурные решения Omni-CIO

Этот файл фиксирует действующие решения для applied Omni-CIO v9.0.0 и последовательно развиваемой V10. Исторические решения не удаляются молча: если правило изменилось reviewed program/release, оно помечается superseded.

## ADR-001 — Production read-only credential remains read-only; Gateway has isolated contours

**Статус:** supersedes прежнее «весь Gateway GET-only».

Production `TINVEST_TOKEN` остаётся read-only и никогда не используется как Real fallback. Gateway теперь содержит три явно изолированных контура:

1. baseline read-only;
2. optional virtual Sandbox;
3. optional exact-owner-confirmed Real BUY/SELL.

Conditional POST Actions допустимы только в reviewed Sandbox/Real surfaces и не означают общий broker-write доступ. Legacy marker `trading_methods=false` сохраняется. Transfer/withdrawal, margin/short, MARKET/BESTPRICE, stop/replace/async и autonomous recurring real execution не входят в reviewed surface.

## ADR-002 — Production entrypoint остаётся `app:app`

**Статус:** принято.

Render и GPT Actions зависят от стабильного FastAPI app. `app_v371.py`, `app_v360.py` и `main.py` остаются, пока `app.py` импортирует их. Консолидация wrappers требует отдельной compatibility migration и полного Regression Shield.

## ADR-003 — Единственный пользовательский интерфейс текущего V9 runtime — существующий Custom GPT v9.0.0

**Статус:** принято для текущего V9 runtime; будущий V10 Web/Telegram не заменяет этот boundary до своих Exit Gates.

Поддерживается один applied GPT:

`Omni-CIO API | Управляющий и аналитик v9.0.0`.

Он был upgraded in place и owner-accepted 2026-08-05. Не создавать duplicate GPT/frontend/Gateway/scheduler как recovery или maintenance shortcut.

Protected rollback UI/Instructions v8.6.1 остаются в GitHub как recovery evidence, а не как current applied version.

## ADR-004 — GitHub является canonical code/config/recovery source, но не external applied-state store

**Статус:** принято.

`main` + tests/contracts являются runtime/recovery source of truth. `gpt/` содержит applied/recovery GPT configuration.

GitHub не нажимает GPT Editor `Update`, не хранит secret values и не синхронизирует Render/GPT/Upstash/QStash автоматически. External applied-state claims требуют owner evidence.

V10 расширяет этот принцип: GitHub является engineering Control Plane для Web/API/AI/Telegram/configuration schemas/migrations/deployment/recovery, но runtime secrets/private portfolio state остаются вне GitHub.

## ADR-005 — Один applied Instructions payload + один protected rollback payload

**Статус:** supersedes v8.4 production-file decision.

Applied GPT Editor Instructions:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`

Protected rollback Instructions:

`gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`

Нельзя создавать competing production Instructions copies. Исторические engineering/reference files не считаются applied payload.

## ADR-006 — Один setup/recovery entrypoint

**Статус:** принято.

Настройка, восстановление и future update flow начинаются с `gpt/SETUP_INDEX.md`. Не создавать competing setup/audit guides, если информацию можно обновить в существующем canonical document.

## ADR-007 — Secrets остаются вне GitHub и разделены по ролям

**Статус:** принято.

Отдельные external roles:

- production read-only broker credential;
- Sandbox broker credential;
- Real execution credential без transfer access;
- Gateway Bearer credential;
- Upstash durable-state credentials;
- Watchtower/QStash credentials.

GitHub хранит только env/role names и placeholders, не values/full account IDs/private broker payloads.

V10 добавляет future Telegram/local-runtime/encryption credentials в тот же принцип: значения остаются runtime-only и выдаются по минимальной роли.

## ADR-008 — Один production Gateway endpoint

**Статус:** принято для текущего V9 runtime.

Canonical service:

`https://omni-cio-gateway.onrender.com`

OpenAPI authority:

`https://omni-cio-gateway.onrender.com/openapi.json`

Не поддерживать старые/альтернативные production service names. V10 не меняет этот runtime endpoint до отдельного accepted deployment/migration package.

## ADR-009 — Portfolio management is tool-first; exact Action isolation preserved

**Статус:** принято.

Baseline portfolio chain:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`.

Exact-action request имеет приоритет и не расширяется. Portfolio management/advisory wording не является Real authorization.

## ADR-010 — Fresh/data-quality gates precede exact market-sensitive sizing or execution

**Статус:** принято.

Stale/incomplete/contradictory data не выдаются как exact executable truth. Last price не является гарантией исполнения. Technical capacity/free cash не превращаются автоматически в personal sizing.

Real preflight дополнительно требует supported identity, fresh trusted market, own-funds BUY/own-position SELL, exact price step, limits и durable state.

## ADR-011 — Moscow is user-visible timezone

**Статус:** принято.

User-visible dates/times используют `Europe/Moscow`/MSK. Trading readiness определяется broker/Gateway state, а не только часами.

V10 persistent canonical timestamps use UTC with explicit source/receive semantics; MSK remains a presentation concern unless later owner policy changes it.

## ADR-012 — CI/dependency supply chain fail-closed

**Статус:** принято.

- human-edited direct dependencies live in `requirements.in` / `requirements-dev.in`;
- generated locks pin exact transitive versions + SHA-256 hashes;
- generated Windows projections are CI artifacts and are not committed;
- external GitHub Actions pin full commit SHA;
- Regression Shield blocks merge on lock/contract/quality/security failure;
- Dependabot PR is a proposal, not merge authorization;
- known-incompatible toolchain versions are held narrowly/documented rather than weakening a gate.

## ADR-013 — v9 master plan remains completed specification/audit trail

**Статус:** принято.

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md` описывает owner-approved WP0–WP15. Program complete; current code/tests/status determine active implementation. Master-plan files remain recovery/history evidence, not an active queue of unfinished work.

## ADR-014 — Repository cleanup must preserve real dependencies and delete one-time artifacts after proof

**Статус:** принято.

Перед удалением файла проверяются imports, tests, CI, configuration and runtime references. Versioned filenames are not automatically legacy.

One-time bootstrap payloads/generated CI projections are removed once their workflow/references are retired and a regression guard prevents return.

## ADR-015 — Effective production OpenAPI is GPT Action authority

**Статус:** принято for current V9 Custom GPT.

Internal WP1–WP14 modules are not automatically GPT Actions. GPT может вызвать/утверждать server execution только для operationId, реально опубликованного effective `/openapi.json` и подтверждённого returned evidence.

Reviewed Real operationIds:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Sandbox outputs всегда virtual. Watchtower scheduler/callback routes hidden from GPT OpenAPI.

V10 Web/Telegram/AI tool authority will use separate reviewed internal contracts; it cannot infer broker authority from the V9 OpenAPI or vice versa.

## ADR-016 — Real execution requires explicit owner confirmation and broker reconciliation

**Статус:** принято.

Real lifecycle:

`fresh facts → immutable proposal/plan context → exact owner confirmation in NEW turn → one idempotent submit → broker reconciliation`.

Ambiguous possible-submit never auto-retries. `submitted` != `filled` without broker evidence. Protected v8.6.1 first-real-order acceptance remains 100% complete and rollback evidence remains valid.

## ADR-017 — Live acceptance validates reviewed authority, not obsolete production-wide GET-only state

**Статус:** принято.

Scheduled live acceptance performs public GETs only to `/health` and `/openapi.json`. It verifies exact reviewed baseline/Sandbox/Real allowlists, methods/paths, consequential markers and forbidden surfaces without sending broker/Gateway credentials or invoking a protected Action.

The baseline GET-only release contract remains useful for safe-mode/unit verification, but is not the production-wide scheduled authority check after reviewed v9 execution contours exist.

## ADR-018 — v9 feature program complete; repository entered controlled maintenance mode

**Статус:** superseded for feature-program governance by ADR-019; remains true for the current V9 runtime maintenance boundary.

WP0–WP15 repository delivery and owner external acceptance are complete. V9 remains in controlled maintenance while V10 is developed and until a specific V10 work package safely replaces a boundary.

Every significant change still follows:

`branch → focused tests/guards → exact-head Regression Shield/security → zero unresolved threads → squash merge`.

## ADR-019 — V10 is the exclusive active feature program; V9 remains protected runtime baseline

**Статус:** accepted by owner `START V10` command, implementation begins at WP0.

**Date:** 2026-08-05  
**Current V10 WP at adoption:** WP0 — Program Lock / Architecture Freeze verification.

### Context

V9 has completed WP0–WP15 and is owner-accepted. The owner approved the canonical V10 Master Plan and subsequently issued explicit `START V10`. V10 must become an account-independent Personal Autonomous Investment Platform without sacrificing current V9 safety/recovery.

### Decision

- V10 is the only authorized feature-development program until its final 100% Definition of Done/owner acceptance.
- Work proceeds strictly WP-by-WP according to `OMNI_CIO_V10_MASTER_PLAN.md`.
- V9 remains the current production/recovery runtime until individual V10 packages explicitly replace a boundary and pass their Exit Gates.
- GitHub is the V10 engineering Control Plane; runtime nodes are replaceable Data Plane instances.
- One Core serves future Web/Telegram/AI adapters; parallel competing stacks are prohibited.
- AI has no direct broker-write authority.
- Current Custom GPT assets are migrated/retained until explicit parity/decommission acceptance.
- Real execution continues to require deterministic constraints, immutable plan, explicit owner approval, idempotency and broker reconciliation.

### Alternatives considered

- continue indefinitely inside Custom GPT only — rejected because it keeps account/platform dependency and weak background autonomy;
- build a second independent site/bot stack — rejected because it duplicates business logic and creates conflicting authorities;
- replace V9 runtime immediately — rejected because it removes proven rollback before V10 is accepted.

### Security / money-authority impact

No authority expansion at WP0. `START V10` is engineering authorization only. V9 read-only/Sandbox/Real boundaries and kill switches remain binding.

### Data / migration impact

None at WP0. V10 persistence/migrations begin only in their later accepted packages.

### Operational impact

Current production remains V9. V10 begins with documentation/governance/architecture freeze, then repository/toolchain/CI before Lenovo setup or feature runtime.

### Failure mode / rollback

If a V10 package fails, stop that package, retain V9 production and recover from the last accepted V10/main state. Do not weaken V9 to force V10 forward.

### Verification

WP0 requires canonical architecture/security/data-flow/threat/recovery docs, ADR process, baseline Regression Shield, no secrets/private payloads, and focused PR acceptance.

### Supersedes

Supersedes ADR-018 only for *feature-program governance*. ADR-018 remains historical evidence and the V9 runtime remains controlled-maintenance/protected until replaced by accepted V10 boundaries.
