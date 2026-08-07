# 00 — OMNI-CIO PROJECT MASTER CONTEXT

Дата актуализации: 2026-08-07

Этот файл хранит короткую долговременную память **одного проекта**: защищённого owner-accepted V9 runtime и последовательно развиваемой автономной платформы V10.

## 1. Product identity

Текущий applied production/recovery baseline:

`Omni-CIO API | Управляющий и аналитик v9.0.0`.

Applied repository sources:

- Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`;
- Knowledge: `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`;
- Gateway: `app:app` on the current Render service;
- protected rollback Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.

Не создавать второй GPT для recovery/maintenance. V10 мигрирует полезные GPT assets в самостоятельную платформу, но текущий GPT остаётся recovery/parity reference до явного decommission gate.

## 2. Protected V9 runtime

```text
EXISTING Omni-CIO GPT v9.0.0
        |
        v
Omni-CIO Gateway (`app:app`)
        |-- production read-only contour
        |-- optional virtual Sandbox contour
        |-- exact-owner-confirmed Real execution contour
        |-- durable state / Watchtower support
        `-- protected V9 engines and recovery contracts
```

V9 WP0–WP15 are complete and owner-accepted. V9 remains controlled maintenance while V10 is built. V10 must not silently replace a V9 runtime boundary before the responsible WP passes its Exit Gate.

Protected v8.6.1 recovery commit:

`baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e`.

Protected execution invariant:

**idempotent replay verified with no second submit**.

## 3. V10 program state

OWNER issued `START V10` on 2026-08-05.

Accepted implementation:

- WP0 — COMPLETE;
- WP1 — COMPLETE;
- WP2 — COMPLETE;
- WP3 — COMPLETE;
- GitHub Pro hybrid CI + Lenovo continuity infrastructure — COMPLETE.

Accepted planning authority additionally includes the concrete local-first AI/Cortex clarification and the OWNER-approved GitHub Pro maximum-utilization/migration-development clarification. Planning amendments do not increase implementation progress by themselves.

Current accepted V10 implementation progress remains **5%** because Block B is credited only after WP4/Block Exit Gate.

**Next authorized implementation package: WP4 — Release, build provenance and deployment contract.**

The planning package that defines GitHub Pro utilization, V9->V10 parity/reuse discipline and WP execution instructions does **not** start WP4.

Exact state authority: `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## 4. V10 authority/navigation

Base program:

- `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`.

Accepted implementation clarifications are indexed by:

- `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`.

Important active authorities include:

- `docs/master-plan/OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_GITHUB_PRO_AND_MIGRATION_IMPLEMENTATION_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `docs/master-plan/OMNI_CIO_V10_GITHUB_PRO_IMPLEMENTATION_CHECKLIST.md`;
- `docs/architecture/V10_AI_CORTEX_CONTRACT.json`;
- `docs/architecture/V10_GITHUB_PRO_UTILIZATION_CONTRACT.json`;
- `docs/architecture/V10_V9_TO_V10_PARITY_LEDGER.json`;
- `docs/architecture/V10_COMPONENT_REUSE_MATRIX.json`;
- `docs/architecture/V10_RELEASE_MANIFEST.schema.json`.

Architectural sources include V10 system/security/data-flow/threat/recovery/ADR/repository/toolchain/Regression-Shield documents under `docs/architecture/`.

Chat memory does not override accepted GitHub authority.

## 5. GitHub Control Plane

Repository: `MishaGameHacking/omni-cio-gateway`.

Accepted `main` before the GitHub-Pro planning PR is:

`5743608389dd0fc6eba4dc33540a61016dc98914`.

Infrastructure PR #242 established:

- private protected `main`;
- squash-only merge discipline;
- required `V10 authoritative merge gate` from GitHub Actions;
- GitHub-hosted fast/clean-room acceleration;
- Lenovo `omni-cio-ci` authoritative heavy Windows gate/continuity;
- successful post-merge Regression Shield on its accepted main.

GitHub Pro is the approved primary engineering subscription/Control Plane. V10 must use the included GitHub capabilities plus Lenovo/open-source components before proposing another recurring paid engineering service.

Approved compute split:

- GitHub-hosted Ubuntu — fast PR feedback;
- GitHub-hosted Windows — disposable, path-aware clean-room/toolchain compatibility;
- Lenovo `omni-cio-ci` — authoritative heavy checks and future local AI/GPU evaluations.

Hosted Actions minutes are acceleration capacity, not the sole compute path. Quota pressure must reduce hosted acceleration rather than weaken exact-head safety gates.

WP4 is planned to establish release manifest/provenance, `v10.*` release identity, native immutable releases where current GitHub support permits, complementary tag protection, path-aware CI, cache/artifact/minute budget controls and exact rollback evidence. It must not start Block C or install the AI runtime.

The Lenovo already being a GitHub runner does **not** mean the V10 application/AI node is implemented. Full node provisioning remains Block C after WP4.

## 6. V10 migration/productization rule

V10 is **not** a greenfield rewrite and is not a feature-expansion exercise.

Default migration flow:

`accepted V9 capability -> identify V10 owner -> parity ledger -> reuse decision -> contract -> smallest implementation -> deterministic parity evidence -> staged cutover -> retirement only after acceptance`.

Every material capability in scope must be represented in `V10_V9_TO_V10_PARITY_LEDGER.json` and end as `PARITY_PROVEN` or explicitly OWNER-approved `INTENTIONALLY_RETIRED` before final V10 acceptance unless the Master Plan assigns it to a later version.

Component preference:

`REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`.

A rewrite requires a concrete security/correctness/runtime/architecture/data-migration reason. Newer/cleaner/easier code or developer/AI preference is not enough.

Every implementation WP uses `OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md` so future engineering sessions know the accepted baseline, allowed changes, explicit non-goals, contracts, failure cases, CI routing, rollback, Exit Gate and evidence before coding.

## 7. Core product principle

V10 is one system with two cooperating layers:

```text
DETERMINISTIC CORE  <---- typed safe tools ---->  OMNI-CIO CORTEX
financial truth                                local intelligence
```

### Deterministic Core

Owns exact financial/accounting facts, validation, normalization, reconciliation, calculations, source identity/freshness and money-path enforcement.

### Omni-CIO Cortex

Owns explanation, bounded research, conversational assistance, orchestration, monitoring and non-authoritative scenarios/drafts.

**AI never replaces deterministic accounting/calculations and never owns broker-write authority.**

## 8. V10 portfolio/accounting target

For the new V10 Web cabinet, the primary accounting/portfolio target is **verified broker HTML account report import**.

Required direction:

- parse data only; never execute report HTML/JS/CSS;
- arbitrary period detection;
- MIME/encoding/size/structure validation;
- SHA-256 duplicate handling;
- normalize positions, cash, trades, commissions, taxes, coupons/dividends and accrued interest;
- review before acceptance;
- archive/history/compare/replace/delete;
- reconciliation and explicit discrepancies;
- truthful recognized/partial/unsupported states;
- no photo/screenshot/OCR portfolio workflow.

MOEX provides supported **current-market enrichment**, not broker accounting truth. V10 must visibly distinguish broker period-end state from current market estimate.

## 9. Canonical data/state rules

Web, Telegram and Cortex consume versioned Core contracts instead of reimplementing financial meaning.

Planned canonical families include portfolio/report/position/cash/trade/reconciliation/risk/evidence/incident/decision/plan/execution/system-health/capability DTOs as their owning WPs arrive.

Cross-system rules:

- Decimal-safe money/quantity representation;
- explicit currency, source and schema version;
- UTC canonical timestamps and `as_of` where material;
- canonical IDs rather than display-name matching;
- `0`, `unknown`, `not_available`, `not_applicable`, `stale`, `partial` are distinct;
- common operational state vocabulary: `READY | PARTIAL | STALE | DEGRADED | BLOCKED | ERROR | OFFLINE | RECOVERING | OWNER_ACTION_REQUIRED`;
- each degraded state says what remains trustworthy and what action becomes blocked.

## 10. Local-first AI baseline

Approved initial baseline:

- model: **Qwen3.5-4B**;
- inference runtime: **Ollama**;
- deployment target: validated 4-bit build such as Q4_K_M;
- Russian is first-class;
- initial context: 8K; 16K only after measured acceptance;
- AI provider remains replaceable;
- no paid AI inference subscription is required for V10 DoD.

AI specialization sequence:

`System Policy → typed Tool Registry → Knowledge/RAG → sanitized evals → local benchmark → QLoRA only if measured persistent gaps remain`.

Do not fine-tune first merely because it is possible.

## 11. 24/7 AI/operator model

V10 Cortex is an **event-driven autonomous operator**, not an endless thinking loop.

Typical triggers include user questions, accepted report imports, discrepancies, stale data, Watchtower events, connector failures, scheduled research refreshes, system-health degradation and missing evidence.

AI outage must produce controlled degraded mode; deterministic Core remains usable.

Initial orchestration candidate: LangGraph OSS with durable checkpoint/resume/HITL behavior behind a replaceable orchestration boundary.

## 12. Research/evidence direction

No-subscription-first research baseline:

- internal SearchProvider interface;
- self-hosted SearXNG first;
- bounded HTTP/document retrieval first;
- Playwright only as bounded JS/browser fallback;
- Evidence Store for source identity, authority class, retrieved/published timestamps, instrument/issuer binding, fact/claim and freshness/contradiction state.

Research priority:

`broker report → MOEX → CBR/regulator → issuer/primary source → reputable secondary source → general Web discovery`.

External retrieved text is untrusted data and cannot grant itself tool/system authority.

## 13. AI/tool authority boundary

AI may autonomously use allowlisted read/analysis/research tools and bounded cache/evidence/checkpoint writes.

AI never receives directly:

- raw trading token;
- arbitrary PostOrder/execute tool;
- transfer/withdrawal authority;
- unrestricted SQL/filesystem/network scanner;
- unrestricted Administrator/PowerShell shell;
- GitHub ruleset/CI/OWNER bypass;
- Real-money confirmation authority.

Destructive/security/admin/secret/merge/Real-money operations remain explicit human/engineering boundaries.

## 14. Real-money boundary

Always preserve until a responsible later V10 WP explicitly replaces and proves a boundary:

- READ, Sandbox and Real credentials isolated;
- no advisory wording/AI/Watchtower/Telegram/GitHub change equals submit authorization;
- Real uses immutable plan/proposal + exact short-lived OWNER confirmation in a new turn + preflight + one idempotent submit + reconciliation;
- ambiguous possible-submit is not automatically retried;
- `submitted != filled` without broker proof;
- no transfer/withdrawal, margin/short, hidden autonomous execution authority.

Master Real rollback: `REAL_TRADING_ENABLED=false`.

## 15. Lenovo role and OWNER participation

Lenovo is the first replaceable Personal runtime node and currently also the GitHub self-hosted runner.

Future V10 node design must arbitrate CI vs AI workload so authoritative CI is not starved by background inference/research/training.

Engineering agent handles GitHub/code/CI directly whenever possible. OWNER participation is requested only for genuinely non-delegable local/account/secret/security actions.

Preferred local workflow:

`PowerShell → Administrator only if necessary → one reviewed idempotent block → PASS/FAIL evidence`.

Permanent AI processes run least-privilege, not permanently as Administrator.

## 16. Subscription/cost direction

Design target is minimum recurring subscriptions.

- GitHub Pro: accepted engineering subscription and primary V10 engineering Control Plane;
- local Qwen/Ollama: no AI inference subscription;
- LangGraph OSS: no required hosted-agent subscription;
- SearXNG: no required search API subscription;
- Playwright: local open-source browser automation;
- paid AI/search/agent/security/CI SaaS: not required for V10 Definition of Done;
- GitHub Enterprise/GitHub Advanced Security products: not required for V10 Definition of Done.

Before any new recurring paid service is added, GitHub Pro + Lenovo + open-source/self-hosted alternatives must be shown insufficient, with cost/lock-in/fallback documented and OWNER approval recorded through an amendment.

GitHub metered usage should use included-usage alerts and budget/stop-usage controls where supported so the accepted Pro subscription is maximized without accidental paid overage.

## 17. Development workflow

Significant changes follow:

`restore GitHub authority → identify exactly one current WP → inspect accepted V9 implementation → update parity/reuse decisions → fill WP execution contract → focused branch → smallest implementation + deterministic tests → cheapest relevant checks → exact-head authoritative gates → resolve blockers → squash merge → post-merge verification → status/parity/provenance update → next WP`.

Do not weaken CI/safety because a tool/model/dependency is inconvenient.

Do not start the full Lenovo V10 runtime, Web, Telegram, AI Cortex or later money authority out of order. Current next package is read from `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.
