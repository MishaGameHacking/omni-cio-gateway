# Документация Omni-CIO

Эта папка — навигационный центр проекта. Она дополняет `knowledge/`, но
не заменяет профильные правила поведения Gateway Actions.

## Быстрый вход

1. `../AGENTS.md` — обязательные правила.
2. `../README.md` — текущее состояние и запуск.
3. `master-plan/README.md` — иерархия исходной спецификации.
4. `master-plan/OMNI_CIO_MASTER_PROMPT_V9.txt` — поисковая текстовая копия плана.
5. `../knowledge/00_PROJECT_MASTER_CONTEXT.md` — стратегическая проектная память.
6. `../knowledge/16_CURRENT_PROGRAM_STATUS.md` — фактический активный этап и оставшиеся пакеты.
7. `architecture/SYSTEM_OVERVIEW.md` — компоненты и границы системы.
8. `architecture/REPOSITORY_STRUCTURE.md` — назначение папок и файлов.
9. `inventory/PROJECT_ASSETS.md` — GitHub и внешние системы.
10. `inventory/FILE_INDEX.md` — индекс runtime, tests, configuration и knowledge.

## Разделы

### Master plan

- `master-plan/README.md`
- `master-plan/OMNI_CIO_MASTER_PROMPT_V9.pdf`
- `master-plan/OMNI_CIO_MASTER_PROMPT_V9.txt`

### Architecture

- `architecture/SYSTEM_OVERVIEW.md`
- `architecture/REPOSITORY_STRUCTURE.md`
- `architecture/DECISIONS.md`
- `architecture/FINAL_DECISION_REVIEW_PRODUCTION_ROUTE_V1.md` — private GET Action, bounded TTL registry, fail-closed HTTP and OpenAPI contract.
- `architecture/FINAL_DECISION_REVIEW_PUBLISHER_V1.md` — internal exact-source publication, concurrency, replacement, eviction and safe observability.
- `architecture/FINAL_DECISION_REVIEW_ORCHESTRATION_V1.md` — end-to-end PR-53…PR-63 composition, first-blocker semantics and unchanged production OpenAPI.
- `architecture/FINAL_DECISION_REVIEW_ACCEPTANCE_EVIDENCE_V1.md` — immutable Render/Gateway/GPT/rollback evidence, SHA-256 proof binding and completion rules.
- `architecture/FINAL_DECISION_REVIEW_WORKFLOW_BRIDGE_V1.md` — production-importable typed workflow boundary, scenario/binding composition, TTL and no-route guarantees.
- `architecture/FINAL_DECISION_REVIEW_WORKFLOW_PRODUCER_V1.md` — exactly-one buy/sell source, risk explanation, no-action behavior and coordinator boundary.
- `architecture/FINAL_DECISION_REVIEW_WORKFLOW_COORDINATOR_V1.md` — canonical acquisition evidence, source freshness/account/direction gates and adapter boundary.
- `architecture/FINAL_DECISION_REVIEW_PRODUCTION_OWNER_CALLABLES_V1.md` — fixed provider dispatchers, exact scenario owner routing, bounded TTL lifecycle and fail-closed startup.
- `architecture/FINAL_DECISION_REVIEW_TRUSTED_OWNER_COMPOSITION_V1.md` — one-shot typed owner materialization, explicit pro-forma binding, fixed-provider invocation and cleanup.
- `architecture/FINAL_DECISION_REVIEW_APPROVED_OWNER_ACQUISITION_V1.md` — server-derived context, exact fresh owner leases, PR-78 invocation and existing 503 mapping.
- `architecture/FINAL_DECISION_REVIEW_APPROVED_OWNER_INSTALLATION_V1.md` — exact typed PR-78 owner-port installation into one PR-79 acquisition call, failure behavior and rollback.
- `architecture/FINAL_DECISION_REVIEW_AUTHENTICATED_ROUTE_CONTEXT_V1.md` — trusted publication seed, existing Bearer gate, exact approved context, bounded capture and rollback.
- `architecture/FINAL_DECISION_REVIEW_APPROVED_OWNER_SNAPSHOTS_V1.md` — post-invocation typed snapshots, exact identity selection and safe rebinding to a fresh authenticated server invocation.
- `architecture/FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_INSTALLATION_V1.md` — post-auth snapshot selection, one PR-80 invocation and bounded redacted evidence.
- `architecture/CBR_KEY_RATE_SOURCE_V1.md` — fixed official Bank of Russia source, bounded streaming, protected XML parsing and fail-closed macro contract.
- `architecture/CBR_KEY_RATE_CACHE_V1.md` — exact-range cache, explicit fresh/stale/unavailable states, single-flight refresh and no-silent-stale policy.
- `architecture/CBR_KEY_RATE_OBSERVABILITY_V1.md` — allowlisted source/cache events with operational metadata only and no financial payload.
- `architecture/CBR_KEY_RATE_ALERT_POLICY_V1.md` — bounded thresholds, pending/fired/recovered state, deduplication, cooldown and no outbound transport.
- `architecture/CBR_KEY_RATE_OPERATIONS_LIFECYCLE_V1.md` — deterministic event/evaluation/evidence composition, bounded retention and safe sink handoff.
- `architecture/MOEX_ISS_TQBR_QUOTE_SOURCE_V1.md` — fixed official public TQBR quote source, strict JSON/identity/freshness boundary and delayed informational-feed flags.
- `architecture/MOEX_ISS_TQBR_QUOTE_CACHE_V1.md` — exact TQBR+SECID cache, two-clock freshness, single-flight refresh and no-silent-stale policy.
- `architecture/MOEX_ISS_TQBR_QUOTE_OBSERVABILITY_V1.md` — pure allowlisted source/cache telemetry without price, SECID, account or upstream payload.
- `architecture/MOEX_ISS_TQBR_QUOTE_ALERT_POLICY_V1.md` — bounded global-only operational thresholds, cooldown, recovery and forged-event rejection without financial thresholds or outbound transport.
- `architecture/MOEX_ISS_TQBR_QUOTE_OPERATIONS_LIFECYCLE_V1.md` — deterministic PR-91/92 composition and bounded fired/recovered global evidence with safe sink ordering.
- `architecture/ACRA_ISSUER_RATING_ACTION_SOURCE_V1.md` — fixed official issuer-level ACRA national-RU rating-action source with strict scope, HTML and failure boundaries.
- `architecture/ACRA_ISSUER_RATING_ACTION_CACHE_V1.md` — fixed-source cache with explicit fresh/stale/unavailable states, single-flight refresh and no-silent-stale policy.
- `architecture/ACRA_ISSUER_RATING_ACTION_OBSERVABILITY_V1.md` — pure source/cache telemetry without issuer, rating, outlook, release URL, publication date or raw HTML.
- `architecture/ACRA_RATING_ACTIONS_ALERT_POLICY_V1.md` — bounded global operational policy, strict canonical-event gate, cooldown/recovery and no external delivery.

### Operations

- `operations/DEPLOYMENT_RUNBOOK.md` — основной gateway.
- `operations/TELEGRAM_REMOVAL_RUNBOOK.md` — одноразовая очистка выведенного Telegram service.
- `operations/RELEASE_CHECKLIST.md`

### Inventory

- `inventory/PROJECT_ASSETS.md`
- `inventory/FILE_INDEX.md`

### Custom GPT

Каноническая конфигурация помощника хранится в `../gpt/`:

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

Для настройки самого бота используйте `../gpt/MY_GPT_SETUP_RUNBOOK.md`; для запуска в новом аккаунте без переноса личных чатов — `../gpt/NEW_ACCOUNT_BOOTSTRAP.md`.

### Retired Telegram integration

Runtime и deployment contract удалены. Решение и запрет случайного
возврата описаны в `../knowledge/12_TELEGRAM_RETIREMENT.txt`, а внешняя
очистка — в `operations/TELEGRAM_REMOVAL_RUNBOOK.md`.

### CI and security

Воспроизводимые dependencies, quality/security gates, начальные thresholds и остаточный долг описаны в `../knowledge/14_CI_SECURITY_BASELINE.txt`.

### Current program status

Фактическая вершина программы, завершённые контуры и следующий безопасный
рабочий пакет фиксируются в `../knowledge/16_CURRENT_PROGRAM_STATUS.md`.
Этот файл используется для активного номера PR; стратегические требования
остаются в `../knowledge/00_PROJECT_MASTER_CONTEXT.md`.

### Domain knowledge

Проверяемые правила конкретных возможностей находятся в `../knowledge/`. Они имеют приоритет над краткими описаниями в `docs/`.

## Что не хранится в GitHub

Секреты, реальные отчёты, полный номер счёта, пользовательские финансовые
данные, сырой CBR XML, сырой MOEX ISS JSON, сырой ACRA HTML, upstream
fault/body/exception text, process-local cache/alert/evidence state и финансовые
значения в observability/alert payload не должны находиться в репозитории.
