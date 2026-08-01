# Документация Omni-CIO

Эта папка — навигационный центр проекта. Она дополняет `knowledge/`, но не
заменяет код, contracts или профильные правила Gateway.

## Быстрый вход

1. `../AGENTS.md` — обязательные правила.
2. `../README.md` — текущее состояние и запуск.
3. `master-plan/README.md` — иерархия исходной спецификации.
4. `master-plan/OMNI_CIO_MASTER_PROMPT_V9.txt` — текстовая копия плана.
5. `../knowledge/00_PROJECT_MASTER_CONTEXT.md` — долговременная память.
6. `../knowledge/16_CURRENT_PROGRAM_STATUS.md` — текущая вершина и audit gates.
7. `audits/PROJECT_AUDIT_2026-08-01.md` — последний полный аудит.
8. `architecture/SYSTEM_OVERVIEW.md` — компоненты и границы.
9. `architecture/REPOSITORY_STRUCTURE.md` — назначение папок и файлов.
10. `inventory/PROJECT_ASSETS.md` — GitHub и внешние системы.
11. `inventory/FILE_INDEX.md` — индекс runtime, tests and knowledge.

Фактический `main` и exact-head GitHub Actions имеют приоритет над временными
номерами PR в документах.

## Разделы

### Master plan

- `master-plan/README.md`
- `master-plan/OMNI_CIO_MASTER_PROMPT_V9.pdf`
- `master-plan/OMNI_CIO_MASTER_PROMPT_V9.txt`

### Audits

- `audits/PROJECT_AUDIT_2026-08-01.md` — проверка `main`, PR #130,
  dependencies, warnings, documentation drift and acceptance gaps.

Аудит фиксирует доказанное состояние на дату проверки. Быстро меняющиеся
сведения об открытых PR и CI нужно перепроверять в GitHub.

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

Each source keeps its own identity, scale and failure contract. A generic
cross-agency identity/scale merge is not implied by this index.

### Operations

- `operations/DEPLOYMENT_RUNBOOK.md` — Gateway deployment.
- `operations/RELEASE_CHECKLIST.md` — release evidence and rollback.
- `operations/LIVE_READ_ONLY_ACCEPTANCE.md` — external acceptance cases.
- `operations/SELF_HOSTED_WINDOWS_RUNNER_SERVICE.md` — bounded read-only
  diagnostics and recovery for the trusted persistent Windows runner.
- `operations/TELEGRAM_REMOVAL_RUNBOOK.md` — retired Telegram cleanup history.

### Inventory

- `inventory/PROJECT_ASSETS.md`
- `inventory/FILE_INDEX.md`

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

GitHub does not apply these files to GPT Editor automatically. Actual schema
import, Bearer configuration, Preview and rollback are external owner actions.

### CI and security

Reproducible dependencies, full-SHA Action pins, quality/security gates and
residual debt are described in:

- `../knowledge/14_CI_SECURITY_BASELINE.txt`
- `operations/SELF_HOSTED_WINDOWS_RUNNER_SERVICE.md`
- `audits/PROJECT_AUDIT_2026-08-01.md`

### Current program status

The current merged top, audit hold, dependency queue and next safe package are
recorded in `../knowledge/16_CURRENT_PROGRAM_STATUS.md`. Verify it against
GitHub before starting work.

### Domain knowledge

Specific financial, data-quality and release rules live in `../knowledge/` and
have priority over short descriptions in this index.

## Retired Telegram integration

Runtime and deployment contract are removed. The decision and anti-regression
rules are in `../knowledge/12_TELEGRAM_RETIREMENT.txt`; external cleanup history
is in `operations/TELEGRAM_REMOVAL_RUNBOOK.md`.

## What must not be stored in GitHub

- tokens, Bearer keys and credentials;
- full account identifiers;
- real reports, operations or positions;
- raw CBR XML, MOEX JSON or rating-agency HTML;
- upstream body/fault/exception text;
- process-local cache, alert or evidence state;
- private financial values in observability payloads;
- runner credential/configuration files or registration tokens.
