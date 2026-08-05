# Документация Omni-CIO

Документация поддерживает **один продукт**: текущий owner-accepted Custom GPT/Gateway V9 runtime и последовательно развиваемую V10 platform в том же репозитории.

Current applied GPT: **v9.0.0**, owner-accepted in place on 2026-08-05.  
Protected rollback: **v8.6.1**.  
Current V9 runtime mode: **controlled maintenance**.  
Active feature program: **Omni-CIO V10**, started by owner command `START V10` on 2026-08-05.

## Быстрый вход

1. `../AGENTS.md` — обязательные правила разработки и current-WP sequence.
2. `../README.md` — продукт, current runtime и V10 navigation.
3. `../knowledge/00_PROJECT_MASTER_CONTEXT.md` — долговременный контекст.
4. `../knowledge/16_CURRENT_PROGRAM_STATUS.md` — текущий V9 applied/runtime baseline.
5. `../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` — текущий V10 progress/current/next WP.
6. `master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md` — V10 scope/precedence/exclusivity.
7. `master-plan/OMNI_CIO_V10_MASTER_PLAN.md` — canonical V10 program.
8. `architecture/V10_SYSTEM_ARCHITECTURE.md` — target V10 architecture.
9. `architecture/REPOSITORY_STRUCTURE.md` — canonical repository ownership/boundaries.
10. `architecture/V10_SECURITY_BOUNDARIES.md` — V10 authority zones.
11. `architecture/V10_DATA_FLOW.md` — canonical V10 data flows.
12. `architecture/V10_THREAT_MODEL.md` — threat catalogue.
13. `architecture/V10_RECOVERY_CONTRACT.md` — recovery/portability contract.
14. `architecture/V10_ADR_PROCESS.md` + `architecture/DECISIONS.md` — architecture governance.
15. `../gpt/SETUP_INDEX.md` — current GPT setup/recovery.
16. `operations/RELEASE_CHECKLIST.md` — current V9 release/acceptance checklist until replaced by later V10 work.

## Master programs

`master-plan/` stores owner-approved programs, program locks and audit trail.

### V10 — active feature program

Canonical artifacts:

- `master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`;
- `master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`;
- `master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
- `master-plan/OMNI_CIO_V10_PLAN_READINESS_AUDIT.md`;
- `master-plan/OMNI_CIO_V10_START_RECORD.md`.

Exact accepted progress and next WP: `../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

### V9 — completed protected runtime program

- `master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md` — completed V9 specification/audit trail;
- V9 WP0–WP15 are implemented and owner-accepted;
- current applied/runtime state is `../knowledge/16_CURRENT_PROGRAM_STATUS.md`.

V9 remains the production/recovery baseline in **controlled maintenance** while V10 is built. A V10 package does not replace a V9 boundary until its responsible Exit Gate passes.

## Architecture

V10 authorities:

- `architecture/V10_SYSTEM_ARCHITECTURE.md`;
- `architecture/REPOSITORY_STRUCTURE.md`;
- `architecture/V10_SECURITY_BOUNDARIES.md`;
- `architecture/V10_DATA_FLOW.md`;
- `architecture/V10_THREAT_MODEL.md`;
- `architecture/V10_RECOVERY_CONTRACT.md`;
- `architecture/V10_ADR_PROCESS.md`;
- `architecture/V10_V9_BASELINE_FREEZE.md`;
- `architecture/DECISIONS.md`.

Current V9 runtime architecture remains documented by `architecture/SYSTEM_OVERVIEW.md` and `architecture/V9_*` files until later V10 migration packages explicitly replace those boundaries.

## Repository boundaries

WP1 defines one deterministic Core under `../omni_cio/` and reserves future V10 roots `../apps/`, `../ai/` and `../infrastructure/` for their owning work packages.

Permanent guard:

`../scripts/check_v10_repository_boundaries.py`

It prevents competing application/execution roots, keeps direct Real/plan-execution authority unique, checks critical Core cycles and protects future Web/Telegram/AI from direct Real authority imports.

## Operations

Current V9 runbooks remain authoritative until replaced:

- `operations/DEPLOYMENT_RUNBOOK.md`;
- `operations/RELEASE_CHECKLIST.md`;
- `operations/SANDBOX_TRADING_RUNBOOK.md`;
- `operations/REAL_TRADING_RELEASE_RUNBOOK.md`;
- `operations/V9_WATCHTOWER_RUNBOOK.md`;
- `operations/LIVE_GATEWAY_AUTHORITY_ACCEPTANCE.md`;
- `operations/DEPENDENCY_MAINTENANCE.md` when accepted;
- `operations/SELF_HOSTED_WINDOWS_RUNNER_SERVICE.md` while Regression Shield uses that runner.

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

- `.github/workflows/regression-shield.yml` — mandatory exact-head merge gate;
- `.github/workflows/live-gateway-authority.yml` — current public live V9 Action-authority gate;
- `../scripts/check_repository_layout.py` — existing V9 structure/runtime guard;
- `../scripts/check_v10_repository_boundaries.py` — permanent V10 repository/authority guard;
- `../scripts/check_ci_security_baseline.py` — CI/dependency/security policy;
- `../scripts/check_gpt_recovery_consistency.py` — current GPT/recovery consistency;
- `../SECURITY.md` — security boundary.

## Dependencies and development reproducibility

Canonical Python dependency sources remain in root because current Render/CI consume them directly:

- `../requirements.in` — runtime direct constraints;
- `../requirements.txt` — generated/hash-locked runtime set;
- `../requirements-dev.in` — CI/test/security direct constraints;
- `../requirements-dev.txt` — generated/hash-locked dev set.

Safe local configuration starts from `../.env.example`; secret values are never committed.

WP2 selects/fixes the exact V10 Python/Node/frontend/PostgreSQL/package-manager baseline. Until WP2 acceptance, do not invent or silently add those future runtime/toolchain dependencies.

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

Не создавать competing setup/audit/inventory/source-of-truth file, если информацию можно обновить в существующем canonical document. Historical records may remain for traceability but cannot override accepted `main`, Program Lock or current status files.
