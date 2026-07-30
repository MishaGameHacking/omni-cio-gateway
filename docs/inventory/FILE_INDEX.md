# Индекс файлов проекта

## Runtime

| Файл | Назначение |
|---|---|
| `app.py` | Актуальный gateway release wrapper, OpenAPI additions, internal workflow bridge и `app:app` |
| `app_v371.py` | Архивный совместимый wrapper purchase-capacity release line |
| `app_v360.py` | Базовый legacy wrapper cash-liquidity release line |
| `main.py` | Историческое ядро gateway, auth, базовые routes и helpers |
| `portfolio_market.py` | Portfolio Market Snapshot |
| `portfolio_analytics.py` | Portfolio Analytics Core |
| `cash_liquidity.py` | Cash & Liquidity Diagnostics |
| `purchase_capacity.py` | Purchase Capacity Preview |
| `purchase_capacity_integrity.py` | Арифметика, комиссии и integrity checks |
| `sdk_order_compat.py` | Совместимость read-only SDK расчётных вызовов |
| `operations_analytics.py` | Operations Analytics & Cash Flow Reconciliation |
| `broker_report_reconciliation/` | Generate/Get official report, pagination и reconciliation |
| `omni_cio/contracts/v1/` | Strict immutable Pydantic contracts v1: provenance, quality, Decimal money, analytics and final review |
| `omni_cio/contracts/v1/final_decision_review_publisher.py` | Immutable internal publication result, replacement/eviction and safety invariants |
| `omni_cio/contracts/v1/final_decision_review_orchestration.py` | Immutable end-to-end result, contiguous-stage and read-only invariants |
| `omni_cio/contracts/v1/final_decision_review_acceptance.py` | Immutable production acceptance evidence, proof digests, counters and completion invariants |
| `omni_cio/contracts/v1/final_decision_review_workflow_bridge.py` | Immutable scenario/binding/orchestration bridge result and safety mirrors |
| `omni_cio/contracts/v1/final_decision_review_workflow_producer.py` | Immutable directional/explanation/bridge producer result and safety mirrors |
| `omni_cio/contracts/v1/final_decision_review_workflow_coordinator.py` | Canonical source acquisition evidence and coordinator result invariants |
| `omni_cio/contracts/v1/final_decision_review_trusted_scenario.py` | Immutable trusted scenario publication result, source identity and safety invariants |
| `omni_cio/release/final_decision_review_route_v1.py` | Production private GET route, bounded source registry, exact post-auth context creation and safe handler boundary |
| `omni_cio/release/final_decision_review_publisher_v1.py` | Trusted process-local exact-source publisher with per-registry concurrency guard |
| `omni_cio/release/final_decision_review_orchestration_v1.py` | PR-53…PR-63 composition, first-blocker handling, safe context seed and internal publication |
| `omni_cio/release/final_decision_review_acceptance_v1.py` | Offline eight-case evidence recorder and complete-dossier collector |
| `omni_cio/release/final_decision_review_workflow_bridge_v1.py` | Production-importable typed risk/pre-trade bridge into PR-63 orchestration |
| `omni_cio/release/final_decision_review_workflow_producer_v1.py` | Exactly-one buy/sell source, risk explanation and PR-65 producer pipeline |
| `omni_cio/release/final_decision_review_workflow_coordinator_v1.py` | Source-evidence, freshness, account and direction coordinator before PR-66 |
| `omni_cio/release/final_decision_review_source_acquisition_v1.py` | Four typed loader ports, safe outcome mapping and exact PR-67 handoff |
| `omni_cio/release/final_decision_review_production_sources_v1.py` | Atomic scenario source store, live current-risk loader and PR-68 production wiring |
| `omni_cio/release/final_decision_review_production_registration_v1.py` | Lazy production runtime registration with shared stores, PR-79/PR-80 boundaries, PR-81 context capture and PR-82 snapshot store |
| `omni_cio/release/final_decision_review_trusted_scenario_publisher_v1.py` | Exact typed gate/risk trust boundary, masked-account parity, freshness and atomic publication |
| `omni_cio/release/final_decision_review_calculator_handoff_v1.py` | PR-72 typed purchase/sell preview handoff into the canonical publisher |
| `omni_cio/release/final_decision_review_calculator_intent_workflow_v1.py` | PR-73 exact capacity-intent gate construction before handoff |
| `omni_cio/release/final_decision_review_approved_invocation_v1.py` | PR-74 allowlisted, freshness/replay-safe invocation and post-success PR-82 snapshot capture |
| `omni_cio/release/final_decision_review_calculator_provider_registry_v1.py` | PR-75 fixed typed calculator-provider registry |
| `omni_cio/release/final_decision_review_existing_calculator_providers_v1.py` | PR-76 adapters from existing read-only calculator owners |
| `omni_cio/release/final_decision_review_production_owner_callables_v1.py` | PR-77 scenario-scoped fixed provider owner routing |
| `omni_cio/release/final_decision_review_trusted_owner_composition_v1.py` | PR-78 one-shot typed owner materialization, pro-forma binding and cleanup |
| `omni_cio/release/final_decision_review_approved_owner_acquisition_v1.py` | PR-79 server-context acquisition, exact fresh owner leases, account binding and safe unavailable mapping |
| `omni_cio/release/final_decision_review_approved_owner_installation_v1.py` | PR-80 exact typed PR-78 owner-port installation into one PR-79 acquisition call |
| `omni_cio/release/final_decision_review_authenticated_route_context_v1.py` | PR-81 trusted seed, post-Bearer approved context derivation and bounded 300-second capture store |
| `omni_cio/release/final_decision_review_approved_owner_snapshots_v1.py` | PR-82 exact typed post-invocation snapshot store and fresh authenticated owner-port rebinding |

## Конфигурация

| Файл | Назначение |
|---|---|
| `render.yaml` | Gateway Render contract |
| `requirements.in` | Human-edited production constraints |
| `requirements.txt` | Полностью pinned production lock с SHA-256 hashes |
| `requirements-dev.in` | Human-edited development constraints |
| `requirements-dev.txt` | Полностью pinned development lock с SHA-256 hashes |
| `pyproject.toml` | Ruff, mypy, pytest/coverage и Bandit baseline |
| `.env.example` | Имена Gateway-переменных без секретных значений |
| `.gitignore` | Защита от секретов и артефактов |
| `.editorconfig` | Единые правила форматирования |

## Tests

| Файл | Область |
|---|---|
| `tests/test_regression_shield.py` | Gateway OpenAPI, auth, read-only и entrypoint |
| `tests/test_final_decision_review_production_route_v1.py` | Production final-review HTTP, source registry, TTL, substitution and OpenAPI contract |
| `tests/test_final_decision_review_publisher_v1.py` | Internal publication, replacement, concurrency, eviction, expiry, restart, observability and unchanged OpenAPI |
| `tests/test_final_decision_review_orchestration_v1.py` | Complete composition, stage blockers, production route validation, publication and immutable result |
| `tests/test_final_decision_review_acceptance_v1.py` | Evidence statuses, SHA-256 binding, dependencies, counters, failure, sensitive-data and offline guards |
| `tests/test_final_decision_review_workflow_bridge_v1.py` | Production bridge registration, exact route, no-action, HTTPS, trace, concurrency, TTL, restart and immutability |
| `tests/test_final_decision_review_workflow_producer_v1.py` | Buy/sell producer, route 200, stale/account no-action, direction count, trace, concurrency and OpenAPI invariance |
| `tests/test_final_decision_review_workflow_coordinator_v1.py` | Complete handoff, missing/failed/stale sources, account/direction mismatch, privacy and producer-call guards |
| `tests/test_final_decision_review_source_acquisition_v1.py` | Loader routing, missing/failed/timeout/type/timestamp mapping and exact coordinator handoff |
| `tests/test_final_decision_review_production_sources_v1.py` | Atomic bundle lifecycle, live current-risk composition, acquisition wiring and write-surface guards |
| `tests/test_final_decision_review_trusted_scenario_publisher_v1.py` | Purchase/sell publication, replacement, freshness, account/direction parity, unsafe policy and concurrency |
| `tests/test_final_decision_review_calculator_handoff_v1.py` | PR-72 typed handoff and canonical publisher integration |
| `tests/test_final_decision_review_calculator_intent_workflow_v1.py` | PR-73 exact intent construction and fail-closed gates |
| `tests/test_final_decision_review_approved_invocation_v1.py` | PR-74 allowlist, replay and freshness boundary |
| `tests/test_final_decision_review_calculator_provider_registry_v1.py` | PR-75 fixed provider registry and context checks |
| `tests/test_final_decision_review_existing_calculator_providers_v1.py` | PR-76 existing calculator adapters |
| `tests/test_final_decision_review_production_owner_callables_v1.py` | PR-77 owner callable store, routing and lifecycle |
| `tests/test_final_decision_review_trusted_owner_composition_v1.py` | PR-78 exact pro-forma binding and one-shot cleanup |
| `tests/test_final_decision_review_approved_owner_acquisition_v1.py` | PR-79 context/source freshness, selection, account binding and safe unavailable behavior |
| `tests/test_final_decision_review_approved_owner_installation_v1.py` | PR-80 concrete typed installation, direction isolation, stale context and startup laziness |
| `tests/test_final_decision_review_authenticated_route_context_v1.py` | PR-81 seed derivation, auth-negative guard, exact 200 capture, TTL/eviction, stale compatibility and 14-GET invariance |
| `tests/test_final_decision_review_approved_owner_snapshots_v1.py` | PR-82 post-success capture, exact identity selection, fresh request rebinding, expiry and startup laziness |
| `tests/test_portfolio_market_snapshot.py` | Рыночная оценка портфеля |
| `tests/test_portfolio_analytics.py` | Структура и концентрация |
| `tests/test_cash_liquidity.py` | Деньги и лимиты |
| `tests/test_purchase_capacity.py` | Purchase preview |
| `tests/test_purchase_capacity_integrity.py` | Арифметическая целостность |
| `tests/test_sdk_order_compat.py` | SDK request compatibility |
| `tests/test_operations_analytics.py` | Операции и cash-flow reconciliation |
| `tests/test_broker_report_reconciliation.py` | Брокерский отчёт и сверка |
| `tests/test_broker_report_async_integrity.py` | `task_id`, `pending`, T-Invest 30058 |
| `tests/test_no_telegram_runtime.py` | Запрет Telegram runtime, config, imports и OpenAPI routes |
| `tests/test_ci_security_baseline.py` | Hash locks, Action SHA pins и secret-report policy |
| `tests/test_versioned_data_contracts_v1.py` | Versioning, Decimal JSON, provenance, masking и strict validation |

## Project memory

| Файл | Назначение |
|---|---|
| `AGENTS.md` | Обязательные правила работы |
| `docs/master-plan/README.md` | Иерархия исходной спецификации и текущих источников истины |
| `docs/master-plan/OMNI_CIO_MASTER_PROMPT_V9.pdf` | Исходный пользовательский master plan v9 |
| `docs/master-plan/OMNI_CIO_MASTER_PROMPT_V9.txt` | Поисковая текстовая копия master plan |
| `knowledge/00_PROJECT_MASTER_CONTEXT.md` | Полный контекст и roadmap |
| `knowledge/16_CURRENT_PROGRAM_STATUS.md` | Фактическая вершина программы и следующий пакет |
| `knowledge/09_MARKET_DATA_AND_BUYING_POWER.txt` | Market и buying-power semantics |
| `knowledge/10_OPERATIONS_ANALYTICS_AND_RECONCILIATION.txt` | Operations semantics |
| `knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt` | Broker-report async semantics |
| `knowledge/12_TELEGRAM_RETIREMENT.txt` | Решение о выводе Telegram runtime из эксплуатации |
| `knowledge/13_COMMUNICATION_STYLE_2026.txt` | Активный стиль ChatGPT без transport-specific runtime |
| `knowledge/14_CI_SECURITY_BASELINE.txt` | Воспроизводимый CI, quality/security gates и debt register |
| `knowledge/15_VERSIONED_DATA_CONTRACTS.txt` | Контракт v1, совместимость и read-only инварианты PR-04 |
| `docs/architecture/DATA_CONTRACTS_V1.md` | Архитектура и migration policy versioned contracts v1 |
| `docs/architecture/FINAL_DECISION_REVIEW_PRODUCTION_ROUTE_V1.md` | Production final-review route, registry, HTTP behavior, acceptance boundary and rollback |
| `docs/architecture/FINAL_DECISION_REVIEW_PUBLISHER_V1.md` | Internal publication contract, concurrency, lifecycle, safety and rollback |
| `docs/architecture/FINAL_DECISION_REVIEW_ORCHESTRATION_V1.md` | End-to-end composition, production schema reconstruction, stage blockers and rollback |
| `docs/architecture/FINAL_DECISION_REVIEW_ACCEPTANCE_EVIDENCE_V1.md` | Eight-case production evidence, proof digests, dependency order and completion rules |
| `docs/architecture/FINAL_DECISION_REVIEW_WORKFLOW_BRIDGE_V1.md` | Typed production bridge, scenario/binding pipeline, fail-closed behavior and remaining live-producer gap |
| `docs/architecture/FINAL_DECISION_REVIEW_WORKFLOW_PRODUCER_V1.md` | Buy/sell source pipeline, risk explanation, no-action behavior and remaining coordinator gap |
| `docs/architecture/FINAL_DECISION_REVIEW_WORKFLOW_COORDINATOR_V1.md` | Canonical acquisition evidence, source gates, privacy boundary and remaining adapter gap |
| `docs/architecture/FINAL_DECISION_REVIEW_PRODUCTION_SOURCES_V1.md` | Live current-risk source, atomic scenario bundle, loader wiring and remaining registration gap |
| `docs/architecture/FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_PUBLICATION_V1.md` | Typed calculator-to-store trust boundary, exact parity, lifecycle, safety and rollback |
| `docs/architecture/FINAL_DECISION_REVIEW_APPROVED_OWNER_INSTALLATION_V1.md` | PR-80 typed owner installation, failure behavior, production boundary and rollback |
| `docs/architecture/FINAL_DECISION_REVIEW_AUTHENTICATED_ROUTE_CONTEXT_V1.md` | PR-81 trusted context seed, post-auth derivation, bounded capture, compatibility and rollback |
| `docs/architecture/FINAL_DECISION_REVIEW_APPROVED_OWNER_SNAPSHOTS_V1.md` | PR-82 typed snapshot capture, identity selection, fresh rebinding and next route-invocation gap |
| `gpt/MY_GPT_SETUP_RUNBOOK.md` | Точная настройка ChatGPT → My GPTs, Actions, Preview и rollback |
| `gpt/` | Восстановление и настройка Custom GPT |
| `docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md` | Одноразовая внешняя очистка Telegram после merge |
| `docs/operations/RELEASE_CHECKLIST.md` | Pre-merge, production and acceptance-evidence checklist |
| `docs/` | Архитектура, inventory и runbooks |

## GitHub automation

| Файл | Назначение |
|---|---|
| `.github/workflows/regression-shield.yml` | Blocking quality, contracts, coverage и security CI |
| `.github/dependabot.yml` | Еженедельные pip и GitHub Actions updates |
| `.github/CODEOWNERS` | Ответственный за области |
| `.github/pull_request_template.md` | Definition of Done для PR |
| `.github/ISSUE_TEMPLATE/` | Безопасные формы задач |
| `.github/copilot-instructions.md` | Канонические правила Copilot |

## Repository checks

| Файл | Назначение |
|---|---|
| `scripts/check_repository_layout.py` | Layout, master-plan presence, retired Telegram/duplicate publisher и broker-write guards |
| `scripts/check_ci_security_baseline.py` | Dependency hashes, Action pins, gates и secret report |

## Правило актуальности

При добавлении, переименовании или удалении ключевого файла обновите этот индекс в том же Pull Request. `scripts/check_repository_layout.py` контролирует обязательный набор.
