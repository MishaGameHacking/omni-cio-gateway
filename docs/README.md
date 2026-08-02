# Документация Omni-CIO

Документация поддерживает один продукт: Custom GPT Omni-CIO и read-only Gateway.

## Быстрый вход

1. `../README.md` — что это, как пользоваться и как обновлять.
2. `../AGENTS.md` — обязательные правила разработки.
3. `../knowledge/00_PROJECT_MASTER_CONTEXT.md` — долговременный контекст.
4. `../knowledge/16_CURRENT_PROGRAM_STATUS.md` — текущий accepted status.
5. `../gpt/SETUP_INDEX.md` — настройка/восстановление Custom GPT.
6. `architecture/SYSTEM_OVERVIEW.md` — текущая архитектура.
7. `architecture/REPOSITORY_STRUCTURE.md` — структура и dependencies.
8. `architecture/DECISIONS.md` — действующие ADR.
9. `operations/DEPLOYMENT_RUNBOOK.md` — Render deployment.
10. `operations/RELEASE_CHECKLIST.md` — release/acceptance checklist.

## Master plan

`master-plan/` хранит исходную спецификацию развития именно Omni-CIO:

- `master-plan/README.md`
- `master-plan/OMNI_CIO_MASTER_PROMPT_V9.pdf`
- `master-plan/OMNI_CIO_MASTER_PROMPT_V9.txt`

Master plan определяет направление, но не доказывает, что future feature уже реализована. Current code/tests/status имеют приоритет для фактического состояния.

## Architecture

Core:

- `architecture/SYSTEM_OVERVIEW.md`
- `architecture/REPOSITORY_STRUCTURE.md`
- `architecture/DECISIONS.md`

Остальные architecture files документируют существующие portfolio, market, quality, rating and final-review modules. Их удаление требует проверки corresponding runtime/tests.

## Operations

Основные runbooks:

- `operations/DEPLOYMENT_RUNBOOK.md`
- `operations/RELEASE_CHECKLIST.md`
- `operations/LIVE_READ_ONLY_ACCEPTANCE.md`
- `operations/SELF_HOSTED_WINDOWS_RUNNER_SERVICE.md` — сохраняется, пока Regression Shield использует соответствующий self-hosted Windows runner.

## Custom GPT

Canonical configuration: `../gpt/`.

Главный файл:

`../gpt/SETUP_INDEX.md`

Production Instructions:

`../gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`

Production Knowledge:

ровно 10 файлов `../gpt/knowledge/`.

GitHub не применяет эти файлы к GPT Editor автоматически. После configuration change владелец вручную применяет затронутые Instructions/Knowledge, выполняет Preview и нажимает `Update`.

## CI/security

- `.github/workflows/regression-shield.yml` — основной merge gate.
- `../scripts/check_repository_layout.py` — active repository structure + broker-write guard.
- `../scripts/check_ci_security_baseline.py` — CI/dependency/security policy.
- `../SECURITY.md` — security boundary.

## Не хранить в GitHub

- T-Invest token;
- Gateway Bearer key value;
- Authorization headers;
- полный broker account ID;
- private broker reports/positions/operations как configuration data;
- Render/GPT secret exports.

## Правило документации

Не создавать новый setup/audit/inventory file, если информацию можно добавить в существующий canonical document. Цель структуры — минимум конфликтующих источников истины.
