# 00 — OMNI-CIO PROJECT MASTER CONTEXT

Дата актуализации: 2026-08-16

Этот файл хранит короткую долговременную память **одного проекта**: защищённого owner-accepted V9 runtime и последовательно развиваемой автономной платформы V10.

**Lifecycle:** long-lived product/context authority, **not a competing progress ledger**. Exact current V10 percentage, accepted WP state and authorized next package are read only from `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` on accepted `main`. Documentation classification: `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`.

## 1. Product identity

Текущий applied production/recovery baseline:

`Omni-CIO API | Управляющий и аналитик v9.0.0`.

Applied repository sources:

- Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`;
- Knowledge: `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`;
- Gateway: `app:app` on the protected current V9 Render service;
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

## 3. V10 program state model

OWNER issued `START V10` on 2026-08-05.

This context file deliberately does not maintain a hard-coded `NEXT` package. Current implementation state is authoritative only in:

`knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

As of the 2026-08-16 documentation audit, that status reports **40% accepted implementation**, WP0–WP22 accepted and **WP22A** as the current authorized functional package, with WP23+ locked. This sentence is a convenience snapshot only; later accepted status changes supersede it automatically.

The Engineering Quality / Pre-CI / Green-Merge governance is accepted and active on `main`. It requires root-cause/blast-radius reasoning, cheap/focused preflight before expensive CI, every applicable exact-head gate to conclude SUCCESS, squash merge, post-merge verification and delayed OWNER product acceptance until after merge/post-merge GREEN.

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
- `docs/master-plan/OMNI_CIO_V10_AUTONOMOUS_PORTFOLIO_GOVERNANCE_AND_COMMERCIAL_MODEL_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_PHONE_ONLY_ENGINEERING_AND_HEADLESS_NODE_OPERATIONS_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_ENGINEERING_QUALITY_AND_GREEN_MERGE_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `docs/architecture/V10_AI_CORTEX_CONTRACT.json`;
- `docs/architecture/V10_GITHUB_PRO_UTILIZATION_CONTRACT.json`;
- `docs/architecture/V10_V9_TO_V10_PARITY_LEDGER.json`;
- `docs/architecture/V10_COMPONENT_REUSE_MATRIX.json`;
- `docs/architecture/V10_RELEASE_MANIFEST.schema.json`;
- `docs/architecture/V10_ENGINEERING_QUALITY_GATE_CONTRACT.json`.

Architectural sources include V10 system/security/data-flow/threat/recovery/ADR/repository/toolchain/Regression-Shield documents under `docs/architecture/`.

Chat memory, old screenshots and package-local historical status headings do not override accepted GitHub authority.

## 5. GitHub Control Plane and Personal Node

Repository: `MishaGameHacking/omni-cio-gateway`.

GitHub Pro is the approved primary engineering subscription/Control Plane. Private protected `main`, PR/squash discipline, exact-head gates, CODEOWNERS, Releases/provenance and GitHub Actions form the engineering authority surface.

Compute/runtime roles:

- GitHub-hosted runners — disposable acceleration/compatibility evidence when current account capacity allows;
- Lenovo `omni-cio-ci` — authoritative heavy Windows CI/continuity lane;
- Lenovo/replacement Personal Node — V10 application/private-state runtime authority;
- external-access providers, when accepted, are access/security transport to the Personal Node rather than a second private-state application host.

The current external GitHub Actions budget/capacity condition is mutable operational state and is governed by `docs/operations/V10_CI_COST_CONTROL_STANDARD.md`; it is not permanent architecture. Never silently change OWNER budget/payment controls.

Accepted V10 source roots now include `apps/api/`, `apps/web/` and Personal-Node infrastructure under `infrastructure/`. Later Telegram and AI roots remain gated by their owning WPs.

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

The deterministic Guardian/Watchtower/Decision system is the primary 24/7 autonomous actor. Cortex is invoked when research/language/interpretation or OWNER dialogue adds value; V10 does not run an endless untriggered LLM thinking loop.

## 8. V10 portfolio/accounting target

For the V10 Web cabinet, the primary accounting/portfolio target is **verified broker HTML account report import**.

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

## 11. Research/evidence direction

No-subscription-first research baseline:

- internal SearchProvider interface;
- self-hosted SearXNG first;
- bounded HTTP/document retrieval first;
- Playwright only as bounded JS/browser fallback;
- Evidence Store for source identity, authority class, retrieved/published timestamps, instrument/issuer binding, fact/claim and freshness/contradiction state.

Research priority:

`broker report → MOEX → CBR/regulator → issuer/primary source → reputable secondary source → general Web discovery`.

External retrieved text is untrusted data and cannot grant itself tool/system authority.

## 12. AI/tool authority boundary

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

## 13. Real-money boundary

Always preserve until a responsible later V10 WP explicitly replaces and proves a boundary:

- READ, Sandbox and Real credentials isolated;
- no advisory wording/AI/Watchtower/Telegram/GitHub change equals submit authorization;
- Real uses immutable plan/proposal + exact short-lived OWNER confirmation in a new turn + preflight + one idempotent submit + reconciliation;
- ambiguous possible-submit is not automatically retried;
- `submitted != filled` without broker proof;
- no transfer/withdrawal, margin/short, hidden autonomous execution authority.

Master Real rollback: `REAL_TRADING_ENABLED=false`.

## 14. OWNER participation and headless operations

The OWNER's normal engineering/product-control surface is a browser/phone flow where feasible. Lenovo/replacement Personal Node should operate headlessly for normal service operation.

Engineering handles GitHub/code/CI/provider automation directly whenever possible. OWNER participation is requested only for genuinely non-delegable account/consent/secret/UAC/admin/physical decisions or actions.

OWNER handoffs follow `docs/operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md`: exact official target when stable, one bounded action, expected result, STOP conditions, do-not-do warnings and minimum non-secret return.

Permanent processes run least privilege, not permanently as Administrator.

## 15. Subscription/cost direction

Design target is minimum recurring subscriptions.

- GitHub Pro: accepted engineering subscription and primary V10 engineering Control Plane;
- local Qwen/Ollama: no AI inference subscription;
- LangGraph OSS: no required hosted-agent subscription;
- SearXNG: no required search API subscription;
- Playwright: local open-source browser automation;
- paid AI/search/agent/security/CI SaaS: not required for V10 Definition of Done;
- GitHub Enterprise/GitHub Advanced Security products: not required for V10 Definition of Done.

Before any new recurring paid service is added, GitHub Pro + Lenovo + open-source/self-hosted alternatives must be shown insufficient, with cost/lock-in/fallback documented and OWNER approval recorded through an amendment.

## 16. Development workflow

Significant changes follow:

`restore GitHub authority → identify exactly one current WP/defect → root-cause/blast-radius review → inspect accepted V9 implementation/parity where relevant → focused implementation + deterministic tests/guards → cheap/focused preflight → full-diff review → all applicable exact-head gates SUCCESS → resolve blockers → squash merge → exact-main post-merge verification → OWNER product acceptance only when required → status/parity/provenance update → next WP`.

Do not weaken CI/safety because a tool/model/dependency is inconvenient. Do not synthesize OWNER physical/runtime evidence. Do not start later functional packages out of order. Current authorization is always read from `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.