# Документация Omni-CIO

Документация поддерживает один продукт: существующий Custom GPT Omni-CIO v9.0.0 и один production Gateway.

Current applied GPT: **v9.0.0**, owner-accepted in place on 2026-08-05.  
Protected rollback: **v8.6.1**.  
Repository mode: **controlled maintenance**.

## Быстрый вход

1. `../README.md` — что это, applied state и maintenance.
2. `../AGENTS.md` — обязательные правила разработки.
3. `../knowledge/00_PROJECT_MASTER_CONTEXT.md` — долговременный контекст.
4. `../knowledge/16_CURRENT_PROGRAM_STATUS.md` — текущий applied/repository status.
5. `../gpt/SETUP_INDEX.md` — настройка/восстановление существующего Custom GPT.
6. `architecture/SYSTEM_OVERVIEW.md` — текущая архитектура.
7. `architecture/REPOSITORY_STRUCTURE.md` — структура и dependency sources.
8. `architecture/DECISIONS.md` — действующие ADR.
9. `operations/DEPLOYMENT_RUNBOOK.md` — Render deployment.
10. `operations/RELEASE_CHECKLIST.md` — release/acceptance checklist.
11. `operations/LIVE_GATEWAY_AUTHORITY_ACCEPTANCE.md` — live `/health` + `/openapi.json` authority gate.
12. `operations/DEPENDENCY_MAINTENANCE.md` — dependency update policy when merged to accepted maintenance baseline.

## Master plan

`master-plan/` хранит owner-approved/program-locked спецификацию v9:

- `master-plan/README.md`
- `master-plan/OMNI_CIO_MASTER_PROMPT_V9.pdf`
- `master-plan/OMNI_CIO_MASTER_PROMPT_V9.txt`
- `master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

WP0–WP15 уже реализованы и приняты. Master plan остаётся specification/audit trail; current code/tests/status имеют приоритет для фактического applied state.

## Architecture

Core:

- `architecture/SYSTEM_OVERVIEW.md`
- `architecture/REPOSITORY_STRUCTURE.md`
- `architecture/DECISIONS.md`

V9 architecture/contracts under `architecture/V9_*` document the implemented routing, policy, universe, research, credit, funds, risk, strategy, optimizer, plans, execution, Watchtower, decision journal and Custom GPT recovery boundaries. Их удаление требует проверки runtime/tests/recovery references.

## Operations

Основные runbooks:

- `operations/DEPLOYMENT_RUNBOOK.md`
- `operations/RELEASE_CHECKLIST.md`
- `operations/SANDBOX_TRADING_RUNBOOK.md`
- `operations/REAL_TRADING_RELEASE_RUNBOOK.md`
- `operations/V9_WATCHTOWER_RUNBOOK.md`
- `operations/LIVE_GATEWAY_AUTHORITY_ACCEPTANCE.md`
- `operations/DEPENDENCY_MAINTENANCE.md` when accepted
- `operations/SELF_HOSTED_WINDOWS_RUNNER_SERVICE.md` — сохраняется, пока Regression Shield использует соответствующий self-hosted Windows runner.

The obsolete production-wide GET-only live acceptance is retired because v9 intentionally supports reviewed conditional Sandbox/Real Action contours. The replacement live-authority check performs public GETs only and validates the exact reviewed OpenAPI surface without executing protected Actions.

## Custom GPT

Canonical applied/recovery configuration: `../gpt/`.

Главный файл:

`../gpt/SETUP_INDEX.md`

Applied Instructions:

`../gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`

Protected rollback Instructions:

`../gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`

Applied Knowledge manifest:

`../gpt/KNOWLEDGE_MANIFEST_V9_0_0.md` — ровно 10 файлов `../gpt/knowledge/`, каждый один раз.

GitHub не применяет файлы к GPT Editor автоматически. Current v9 owner acceptance уже выполнен; будущий configuration change снова требует Preview и `Update` на **том же** GPT.

## Actions

Static reviewed catalog: `../gpt/ACTIONS_CATALOG.md`.  
Runtime authority: production `https://omni-cio-gateway.onrender.com/openapi.json`.

Internal v9 Python modules are not automatically Actions. Only operationIds actually published by effective OpenAPI may be called/claimed as server execution.

## CI/security

- `.github/workflows/regression-shield.yml` — основной exact-head merge gate.
- `.github/workflows/live-gateway-authority.yml` — public live Action-authority gate.
- `../scripts/check_repository_layout.py` — repository structure + broker-write guard.
- `../scripts/check_ci_security_baseline.py` — CI/dependency/security policy.
- `../scripts/check_gpt_recovery_consistency.py` — applied v9/recovery consistency.
- `../SECURITY.md` — security boundary.

## Dependencies

Canonical files остаются в root, потому что их напрямую используют Render и CI:

- `../requirements.in` — runtime direct constraints;
- `../requirements.txt` — generated/hash-locked runtime set;
- `../requirements-dev.in` — CI/test/security direct constraints;
- `../requirements-dev.txt` — generated/hash-locked dev set.

Generated Windows projection files are CI artifacts and must not be committed. Dependabot creates proposals only; merge requires current-main exact-head Regression Shield/security.

## Не хранить в GitHub

- T-Invest token values;
- Gateway Bearer key value;
- Upstash/QStash secret values;
- Authorization headers;
- полный broker account ID;
- private broker reports/positions/operations как configuration data;
- Render/GPT secret exports.

## Правило документации

Не создавать новый setup/audit/inventory file, если информацию можно добавить в существующий canonical document. Цель структуры — минимум конфликтующих источников истины и явное разделение applied state, rollback evidence и historical specification.
