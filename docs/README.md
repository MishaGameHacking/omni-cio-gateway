# Документация Omni-CIO

Документация поддерживает **один продукт** и одну forward V10 line. V9 теперь является migration/recovery source внутри текущего lineage, а не отдельно развиваемым будущим runtime.

Current applied GPT: **v9.0.0**, owner-accepted in place on 2026-08-05.  
Protected rollback: **v8.6.1**.  
Current convergence mode: **Amendment 20 / V9C-B deterministic source relocation**.  
Active feature program: **Omni-CIO V10**, started by owner command `START V10` on 2026-08-05.

## Быстрый вход

1. `../AGENTS.md` — обязательные правила разработки и current-WP sequence.
2. `../README.md` — продукт, repository front door и concise current snapshot.
3. `DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md` — какие документы являются current authority, stable contract или historical evidence.
4. `../knowledge/00_PROJECT_MASTER_CONTEXT.md` — долговременный контекст без competing progress ledger.
5. `../knowledge/16_CURRENT_PROGRAM_STATUS.md` — текущий V9 applied/runtime baseline.
6. `../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` — **единственный current V10 progress/current-next WP ledger**.
7. `master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md` — V10 scope/precedence/exclusivity.
8. `master-plan/OMNI_CIO_V10_MASTER_PLAN.md` — canonical V10 program.
9. `master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md` — accepted active amendments.
10. `architecture/V10_SYSTEM_ARCHITECTURE.md` — target/accepted V10 architecture.
11. `architecture/REPOSITORY_STRUCTURE.md` — canonical repository ownership/boundaries.
12. `architecture/V10_SECURITY_BOUNDARIES.md` — V10 authority zones.
13. `architecture/V10_DATA_FLOW.md` — canonical V10 data flows.
14. `architecture/V10_THREAT_MODEL.md` — threat catalogue.
15. `architecture/V10_RECOVERY_CONTRACT.md` — recovery/portability contract.
16. `architecture/V10_ADR_PROCESS.md` + `architecture/DECISIONS.md` — architecture governance.
17. `../gpt/SETUP_INDEX.md` — current GPT setup/recovery.
18. `operations/RELEASE_CHECKLIST.md` — protected V9 release/acceptance checklist until its owning migration retires it.

## Master programs

`master-plan/` stores owner-approved programs, program locks, amendments and audit trail.

### V10 — active feature program

Canonical artifacts:

- `master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`;
- `master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`;
- `master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
- `master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`;
- `master-plan/OMNI_CIO_V10_PLAN_READINESS_AUDIT.md` — historical readiness snapshot;
- `master-plan/OMNI_CIO_V10_START_RECORD.md` — historical start snapshot.

Exact accepted progress and next WP: `../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

### V9 — completed migration/recovery source

- `master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md` — completed V9 specification/audit trail;
- V9 WP0–WP15 are implemented and owner-accepted;
- current applied/runtime state is `../knowledge/16_CURRENT_PROGRAM_STATUS.md`.

V9 remains historical capability/recovery evidence while Amendment 20 migrates its remaining working-tree dependencies into V10. A V9 boundary is removed only after its responsible parity, zero-consumer and recovery gate passes.

## Architecture

V10 authorities include:

- `architecture/V10_SYSTEM_ARCHITECTURE.md`;
- `architecture/REPOSITORY_STRUCTURE.md`;
- `architecture/V10_SECURITY_BOUNDARIES.md`;
- `architecture/V10_DATA_FLOW.md`;
- `architecture/V10_THREAT_MODEL.md`;
- `architecture/V10_RECOVERY_CONTRACT.md`;
- `architecture/V10_ADR_PROCESS.md`;
- `architecture/V10_V9_BASELINE_FREEZE.md`;
- `architecture/V10_TOOLCHAIN_BASELINE.md` + machine-readable companion;
- `architecture/V10_ENGINEERING_QUALITY_GATE_CONTRACT.json`;
- `architecture/DECISIONS.md`.

`architecture/SYSTEM_OVERVIEW.md` now describes the current V10/Timeweb source composition and Amendment-20 migration boundary. `architecture/V9_*` files remain historical/recovery evidence unless a later current contract explicitly references them.

## Repository boundaries

`../omni_cio/` is the one deterministic Core root.

Current accepted physical V10 roots include:

- `../apps/api/` — accepted V10 API/application adapter;
- `../apps/web/` — accepted single V10 Web App developed through the accepted Block E packages;
- `../infrastructure/windows/` — accepted Personal-Node/Windows infrastructure from its owning packages.

Later roots remain lifecycle-gated: `../apps/telegram/` and `../ai/` are not authorized merely because the architecture reserves their ownership locations.

The V9 root wrappers remain temporary V9C-C migration inputs; V9-specific `gpt/` and retired-provider artifacts remain V9C-D/V9C-E inputs until their parity/zero-consumer/recovery gates.

Permanent structural guard:

`../scripts/check_v10_repository_boundaries.py`

It prevents competing application/execution roots, keeps direct Real/plan-execution authority unique, checks critical Core cycles and protects presentation/AI layers from direct Real authority imports.

## Operations

Protected V9 runbooks remain authoritative for their still-applied V9 boundaries until explicitly replaced. V10 package runbooks remain package-scoped operational/acceptance records under the lifecycle rule.

Key operations sources include:

- `operations/DEPLOYMENT_RUNBOOK.md`;
- `operations/RELEASE_CHECKLIST.md`;
- `operations/SANDBOX_TRADING_RUNBOOK.md`;
- `operations/REAL_TRADING_RELEASE_RUNBOOK.md`;
- `operations/V9_WATCHTOWER_RUNBOOK.md`;
- `operations/LIVE_GATEWAY_AUTHORITY_ACCEPTANCE.md`;
- `operations/DEPENDENCY_MAINTENANCE.md`;
- `operations/SELF_HOSTED_WINDOWS_RUNNER_SERVICE.md`;
- `operations/V10_CI_COST_CONTROL_STANDARD.md`;
- `operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md`;
- `operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`.

## Current Custom GPT

Canonical applied/recovery configuration remains `../gpt/` until the explicit V10 GPT parity/decommission gate.

Main entry: `../gpt/SETUP_INDEX.md`.  
Applied Instructions: `../gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`.  
Protected rollback Instructions: `../gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.  
Applied Knowledge manifest: `../gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`.

GitHub does not apply files to GPT Editor automatically. Future GPT-visible changes require reviewed repository change and owner Preview/`Update` on the same GPT unless a later accepted V10 package retires that interface.

## Actions and money authority

Static current GPT catalog: `../gpt/ACTIONS_CATALOG.md`.  
Runtime GPT authority: production `https://omni-cio-gateway.onrender.com/openapi.json`.

Internal Python modules are not automatically Actions. `START V10`, AI output, a monitoring alert or development acceptance is not broker-submit authorization.

Current V9 Real execution remains exact-owner-confirmed, immutable, idempotent and broker-reconciled. AI has no direct broker-write authority under V10 architecture.

## CI/security

- `.github/workflows/regression-shield.yml` — mandatory authoritative regression/security verification where applicable;
- `.github/workflows/v10-engineering-governance.yml` — engineering-quality, cost-control and documentation-consistency governance;
- `.github/workflows/live-gateway-authority.yml` — protected public live V9 Action-authority gate when its trusted route is available/applicable;
- `../scripts/check_repository_layout.py` — existing V9 structure/runtime guard;
- `../scripts/check_v10_repository_boundaries.py` — permanent V10 repository/authority guard;
- `../scripts/check_v10_engineering_governance.py` — permanent engineering-governance guard;
- `../scripts/check_v10_documentation_consistency.py` — permanent current-vs-historical documentation guard;
- `../scripts/check_ci_security_baseline.py` — CI/dependency/security policy;
- `../scripts/check_gpt_recovery_consistency.py` — current GPT/recovery consistency;
- `../SECURITY.md` — security boundary.

Applicable exact-head checks must conclude SUCCESS before merge. Infrastructure/billing/provider failures are diagnosed separately from code failures but are never re-labeled as PASS.

## Dependencies and development reproducibility

Canonical Python dependency sources remain in root because current CI/protected V9 runtime consume them directly:

- `../requirements.in` — runtime direct constraints;
- `../requirements.txt` — generated/hash-locked runtime set;
- `../requirements-dev.in` — CI/test/security direct constraints;
- `../requirements-dev.txt` — generated/hash-locked dev set.

Safe local configuration starts from `../.env.example`; secret values are never committed.

WP2 **already selected and accepted** the exact V10 Python/Node/frontend/PostgreSQL/package-manager baseline. Canonical technical versions/evidence are in `architecture/V10_TOOLCHAIN_BASELINE.md` and its machine-readable companion. Later upgrades must follow the accepted dependency/reproducibility/rollback rules; “latest” is not automatically selected.

## Не хранить в GitHub

- T-Invest token values;
- Gateway Bearer key value;
- future Telegram/encryption/runtime secret values;
- Upstash/QStash secret values;
- Authorization headers;
- полный broker account ID;
- private broker reports/positions/operations как repository configuration;
- Render/GPT secret exports.

## Правило документации

Не создавать competing setup/audit/inventory/source-of-truth file, если информацию можно обновить в существующем canonical document. Historical records remain for traceability but cannot override accepted `main`, Program Lock, accepted amendments or current status files.

For document lifecycle, use `DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`. A package-local `PENDING`/`CURRENT` status is interpreted at that package's recorded time unless the file is explicitly in the live current-authority layer.