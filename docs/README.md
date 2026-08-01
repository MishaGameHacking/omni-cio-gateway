# Документация Omni-CIO

Эта папка — навигационный центр проекта. Она дополняет `knowledge/`, но не заменяет код, contracts, фактический GPT Editor или профильные правила Gateway.

## Быстрый вход

1. `../AGENTS.md` — обязательные правила.
2. `../README.md` — текущее состояние и запуск; SHA и active package всегда перепроверять в GitHub.
3. `master-plan/README.md` — иерархия спецификаций и migration rule.
4. `master-plan/OMNI_CIO_FINAL_STEP_BY_STEP_MASTER_PROMPT_RU_V1.md` — текущий GPT-only порядок исполнения.
5. `master-plan/OMNI_CIO_MASTER_PROMPT_V9.txt` — исходная стратегическая спецификация.
6. `../knowledge/00_PROJECT_MASTER_CONTEXT.md` — долговременная память, требующая проверки на drift.
7. `../knowledge/16_CURRENT_PROGRAM_STATUS.md` — оперативный статус, требующий проверки на drift.
8. `audits/GPT_ONLY_AUDIT_START_2026-08-01.md` — начало Stage 0 по финальному плану.
9. `audits/PROJECT_AUDIT_2026-08-01.md` — предыдущий repository-wide аудит.
10. `architecture/SYSTEM_OVERVIEW.md` — компоненты и границы.
11. `architecture/REPOSITORY_STRUCTURE.md` — назначение папок и файлов.
12. `inventory/PROJECT_ASSETS.md` — GitHub и внешние системы.
13. `inventory/FILE_INDEX.md` — индекс runtime, tests and knowledge.

Фактический `main`, GPT Editor и exact-head/merge-ref GitHub Actions имеют приоритет над временными номерами PR и устаревшими status-файлами.

## Разделы

### Master plans

- `master-plan/README.md`
- `master-plan/OMNI_CIO_FINAL_STEP_BY_STEP_MASTER_PROMPT_RU_V1.md`
- `master-plan/OMNI_CIO_MASTER_PROMPT_V9.pdf`
- `master-plan/OMNI_CIO_MASTER_PROMPT_V9.txt`

Финальный план v1.0 задаёт текущий порядок выполнения и уточняет продукт как существующий Custom GPT внутри ChatGPT. Исходный v9 сохраняет стратегические финансовые и архитектурные требования. Конфликты разрешаются только через свежий GPT-only audit, а не выборочное продолжение старого roadmap.

### Audits

- `audits/GPT_ONLY_AUDIT_START_2026-08-01.md` — scope declaration, проверка owner PDF, свежий снимок current main/PR #31/CI, официальные platform rules и подтверждённый documentation drift.
- `audits/PROJECT_AUDIT_2026-08-01.md` — предыдущая проверка `main`, PR #130, dependencies, warnings, documentation drift and acceptance gaps.

Аудит фиксирует доказанное состояние на дату проверки. Быстро меняющиеся сведения об открытых PR, CI, Render и GPT Editor нужно перепроверять.

### Architecture

Core:

- `architecture/SYSTEM_OVERVIEW.md`
- `architecture/REPOSITORY_STRUCTURE.md`
- `architecture/DECISIONS.md`

Final-review chain:

- `architecture/FINAL_DECISION_REVIEW_PRODUCTION_ROUTE_V1.md`
- `architecture/FINAL_DECISION_REVIEW_PUBLISHER_V1.md`
- `architecture/FINAL_DECISION_REVIEW_ORCHESTRATION_V1.md`
- `architecture/FINAL_DECISION_REVIEW_ACCEPTANCE_EVIDENCE_V1.md`
- `architecture/FINAL_DECISION_REVIEW_WORKFLOW_BRIDGE_V1.md`
- `architecture/FINAL_DECISION_REVIEW_WORKFLOW_PRODUCER_V1.md`
- `architecture/FINAL_DECISION_REVIEW_WORKFLOW_COORDINATOR_V1.md`
- `architecture/FINAL_DECISION_REVIEW_PRODUCTION_OWNER_CALLABLES_V1.md`
- `architecture/FINAL_DECISION_REVIEW_TRUSTED_OWNER_COMPOSITION_V1.md`
- `architecture/FINAL_DECISION_REVIEW_APPROVED_OWNER_ACQUISITION_V1.md`
- `architecture/FINAL_DECISION_REVIEW_APPROVED_OWNER_INSTALLATION_V1.md`
- `architecture/FINAL_DECISION_REVIEW_AUTHENTICATED_ROUTE_CONTEXT_V1.md`
- `architecture/FINAL_DECISION_REVIEW_APPROVED_OWNER_SNAPSHOTS_V1.md`
- `architecture/FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_INSTALLATION_V1.md`

Official source chains:

- `architecture/CBR_KEY_RATE_SOURCE_V1.md`
- `architecture/CBR_KEY_RATE_CACHE_V1.md`
- `architecture/CBR_KEY_RATE_OBSERVABILITY_V1.md`
- `architecture/CBR_KEY_RATE_ALERT_POLICY_V1.md`
- `architecture/CBR_KEY_RATE_OPERATIONS_LIFECYCLE_V1.md`
- `architecture/MOEX_ISS_TQBR_QUOTE_SOURCE_V1.md`
- `architecture/MOEX_ISS_TQBR_QUOTE_CACHE_V1.md`
- `architecture/MOEX_ISS_TQBR_QUOTE_OBSERVABILITY_V1.md`
- `architecture/MOEX_ISS_TQBR_QUOTE_ALERT_POLICY_V1.md`
- `architecture/MOEX_ISS_TQBR_QUOTE_OPERATIONS_LIFECYCLE_V1.md`
- `architecture/ACRA_ISSUER_RATING_ACTION_SOURCE_V1.md`
- `architecture/ACRA_ISSUER_RATING_ACTION_CACHE_V1.md`
- `architecture/ACRA_ISSUER_RATING_ACTION_OBSERVABILITY_V1.md`
- `architecture/ACRA_RATING_ACTIONS_ALERT_POLICY_V1.md`
- `architecture/ACRA_RATING_ACTIONS_OPERATIONS_LIFECYCLE_V1.md`
- `architecture/EXPERT_RA_ISSUER_RATING_ACTION_SOURCE_V1.md`
- `architecture/EXPERT_RA_ISSUER_RATING_ACTION_CACHE_V1.md`
- `architecture/EXPERT_RA_ISSUER_RATING_ACTION_OBSERVABILITY_V1.md`
- `architecture/EXPERT_RA_RATING_ACTIONS_ALERT_POLICY_V1.md`
- `architecture/EXPERT_RA_RATING_ACTIONS_OPERATIONS_LIFECYCLE_V1.md`
- `architecture/NCR_ISSUER_RATING_ACTION_SOURCE_V1.md`

Each source keeps its own identity, scale and failure contract. A generic cross-agency identity/scale merge is not implied.

The existence of an architecture file does not prove current Custom GPT end-to-end use. Stage 1 must classify every chain as active, compatibility, reusable, optional future, deprecated, orphaned or conflicting.

### Operations

- `operations/DEPLOYMENT_RUNBOOK.md` — Gateway deployment.
- `operations/RELEASE_CHECKLIST.md` — release evidence and rollback.
- `operations/LIVE_READ_ONLY_ACCEPTANCE.md` — external acceptance cases.
- `operations/SELF_HOSTED_WINDOWS_RUNNER_SERVICE.md` — bounded read-only diagnostics and recovery for the trusted persistent Windows runner.
- `operations/TELEGRAM_REMOVAL_RUNBOOK.md` — retired Telegram cleanup history.

### Inventory

- `inventory/PROJECT_ASSETS.md`
- `inventory/FILE_INDEX.md`

Inventory must be reclassified against the GPT-only user journey. Separate site/frontend work is not an active product requirement unless the owner later changes scope.

### Custom GPT

Canonical configuration lives in `../gpt/`:

- `../gpt/README.md`
- `../gpt/MY_GPT_SETUP_RUNBOOK.md`
- `../gpt/CONFIGURATION.md`
- `../gpt/INSTRUCTIONS.md`
- `../gpt/INSTRUCTIONS_COMPACT.md`
- `../gpt/ACTIONS_CATALOG.md`
- `../gpt/NEW_CHAT_PROMPT.md`
- `../gpt/PROJECT_INSTRUCTIONS.md`
- `../gpt/BOT_ONLY_FILE_MANIFEST.md`
- `../gpt/NEW_ACCOUNT_BOOTSTRAP.md`

GitHub does not apply these files to GPT Editor automatically. Actual schema import, Bearer configuration, capabilities, Preview, Update and rollback are owner/external actions. Repository files must be compared with the factual existing GPT before being treated as deployed.

### CI and security

Reproducible dependencies, full-SHA Action pins, quality/security gates and residual debt are described in:

- `../knowledge/14_CI_SECURITY_BASELINE.txt`
- `operations/SELF_HOSTED_WINDOWS_RUNNER_SERVICE.md`
- `audits/PROJECT_AUDIT_2026-08-01.md`
- `audits/GPT_ONLY_AUDIT_START_2026-08-01.md`

### Current program status

The operational status is recorded in `../knowledge/16_CURRENT_PROGRAM_STATUS.md`, but the GPT-only audit has already confirmed drift in its main SHA, dependency state and next-package order. It must not be used without checking GitHub and the final plan.

### Domain knowledge

Specific financial, data-quality and release rules live in `../knowledge/`. During Stage 4 they must be reorganized into a compact, versioned library without conflicting copies or critical workflow hidden outside Instructions.

## Retired Telegram integration

Runtime and deployment contract are removed. The decision and anti-regression rules are in `../knowledge/12_TELEGRAM_RETIREMENT.txt`; external cleanup history is in `operations/TELEGRAM_REMOVAL_RUNBOOK.md`.

The current product may prepare Telegram drafts for manual publication. It must not operate as a Telegram chatbot or publish automatically.

## What must not be stored in GitHub

- tokens, Bearer keys and credentials;
- full account identifiers;
- real reports, operations or positions;
- raw CBR XML, MOEX JSON or rating-agency HTML;
- upstream body/fault/exception text;
- process-local cache, alert or evidence state;
- private financial values in observability payloads;
- runner credential/configuration files or registration tokens.
