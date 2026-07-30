# Индекс файлов проекта

## Runtime

| Файл | Назначение |
|---|---|
| `app.py` | Актуальный gateway release wrapper, OpenAPI additions, internal workflow bridge и `app:app` |
| `app_v371.py` / `app_v360.py` | Архивные совместимые wrappers |
| `main.py` | Историческое ядро gateway, auth, базовые routes и helpers |
| `portfolio_market.py` | Portfolio Market Snapshot |
| `portfolio_analytics.py` | Portfolio Analytics Core |
| `cash_liquidity.py` | Cash & Liquidity Diagnostics |
| `purchase_capacity.py` / `purchase_capacity_integrity.py` | Purchase preview и integrity checks |
| `sdk_order_compat.py` | Совместимость read-only SDK расчётных вызовов |
| `operations_analytics.py` | Operations Analytics & Cash Flow Reconciliation |
| `broker_report_reconciliation/` | Generate/Get official report, pagination и reconciliation |
| `omni_cio/contracts/v1/` | Strict immutable Pydantic contracts v1 |
| `omni_cio/contracts/v1/macro.py` | PR-84/85 key-rate source and explicit cache result contracts |
| `omni_cio/contracts/v1/alerting.py` | PR-87/88 CBR alert policy, evaluation and evidence contracts |
| `omni_cio/contracts/v1/moex.py` | PR-89/90 MOEX ISS TQBR source and explicit cache result contracts |
| `omni_cio/contracts/v1/moex_alerting.py` | PR-92 global-only MOEX operational alert policy/evaluation contracts |
| `omni_cio/market/` | Market, capacity, bond, equity, fund and technical analysis |
| `omni_cio/market/cbr_key_rate_v1.py` | PR-84 fixed official Bank of Russia SOAP source, bounded streaming and protected XML parsing |
| `omni_cio/market/cbr_key_rate_cache_v1.py` | PR-85 exact-range bounded cache, single-flight refresh and explicit fresh/stale/unavailable lifecycle |
| `omni_cio/market/moex_iss_quote_v1.py` | PR-89 fixed official public MOEX ISS TQBR quote source, strict JSON validation and bounded transport |
| `omni_cio/market/moex_iss_quote_cache_v1.py` | PR-90 exact TQBR+SECID bounded cache, two-clock freshness, single-flight and no-silent-stale lifecycle |
| `omni_cio/observability/safe_events_v1.py` | Existing allowlisted structured event builder and JSON emitter |
| `omni_cio/observability/cbr_key_rate_events_v1.py` | PR-86 source/cache status, latency, freshness and safe-count telemetry without financial payload |
| `omni_cio/observability/cbr_key_rate_alert_policy_v1.py` | PR-87 bounded thresholds, cooldown, deduplication, recovery and retention lifecycle |
| `omni_cio/observability/cbr_key_rate_operations_lifecycle_v1.py` | PR-88 deterministic event/evaluation/evidence composition and bounded safe sink handoff |
| `omni_cio/observability/moex_iss_quote_events_v1.py` | PR-91 pure MOEX source/cache status builders without price, SECID, account or upstream payload |
| `omni_cio/observability/moex_iss_quote_alert_policy_v1.py` | PR-92 canonical-event gate and bounded global operational alert state machine |
| `omni_cio/release/final_decision_review_route_v1.py` | Production private GET route and safe handler boundary |
| `omni_cio/release/final_decision_review_publisher_v1.py` | Trusted process-local exact-source publisher |
| `omni_cio/release/final_decision_review_orchestration_v1.py` | PR-53…PR-63 composition and first-blocker handling |
| `omni_cio/release/final_decision_review_acceptance_v1.py` | Offline eight-case production acceptance collector |
| `omni_cio/release/final_decision_review_workflow_bridge_v1.py` | Typed production workflow bridge |
| `omni_cio/release/final_decision_review_workflow_producer_v1.py` | Directional producer pipeline |
| `omni_cio/release/final_decision_review_workflow_coordinator_v1.py` | Source freshness/account/direction coordinator |
| `omni_cio/release/final_decision_review_source_acquisition_v1.py` | Typed source acquisition adapter |
| `omni_cio/release/final_decision_review_production_sources_v1.py` | Atomic scenario source store and live current-risk loader |
| `omni_cio/release/final_decision_review_production_registration_v1.py` | Lazy runtime registration through PR-83 |
| `omni_cio/release/final_decision_review_calculator_handoff_v1.py` | PR-72 typed purchase/sell preview handoff |
| `omni_cio/release/final_decision_review_calculator_intent_workflow_v1.py` | PR-73 exact capacity-intent gate |
| `omni_cio/release/final_decision_review_approved_invocation_v1.py` | PR-74 invocation and post-success PR-82 snapshot capture |
| `omni_cio/release/final_decision_review_calculator_provider_registry_v1.py` | PR-75 fixed provider registry |
| `omni_cio/release/final_decision_review_existing_calculator_providers_v1.py` | PR-76 existing read-only calculator adapters |
| `omni_cio/release/final_decision_review_production_owner_callables_v1.py` | PR-77 scenario-scoped owner routing |
| `omni_cio/release/final_decision_review_trusted_owner_composition_v1.py` | PR-78 one-shot typed owner materialization and cleanup |
| `omni_cio/release/final_decision_review_approved_owner_acquisition_v1.py` | PR-79 server-context owner acquisition |
| `omni_cio/release/final_decision_review_approved_owner_installation_v1.py` | PR-80 exact typed owner installation |
| `omni_cio/release/final_decision_review_authenticated_route_context_v1.py` | PR-81 post-Bearer context derivation and bounded capture |
| `omni_cio/release/final_decision_review_approved_owner_snapshots_v1.py` | PR-82 exact typed snapshot store and fresh rebinding |
| `omni_cio/release/final_decision_review_authenticated_owner_installation_v1.py` | PR-83 post-auth selection, one PR-80 invocation and bounded evidence |

## Конфигурация

| Файл | Назначение |
|---|---|
| `render.yaml` | Единственный Gateway Render contract |
| `requirements.in` / `requirements.txt` | Production constraints и hash-locked runtime lock |
| `requirements-dev.in` / `requirements-dev.txt` | Development constraints и hash-locked dev lock |
| `pyproject.toml` | Ruff, mypy, pytest/coverage и Bandit baseline |
| `.env.example` | Имена Gateway-переменных без секретных значений |
| `.gitignore` / `.editorconfig` | Защита от артефактов и единое форматирование |

## Tests

| Файл | Область |
|---|---|
| `tests/test_regression_shield.py` | Gateway OpenAPI, auth, read-only и entrypoint |
| `tests/test_final_decision_review_*` | PR-50…PR-83 contracts, route, lifecycle, owners, acceptance and invariance |
| `tests/test_final_decision_review_authenticated_owner_installation_v1.py` | PR-83 post-auth success/failure/evidence/idempotent registration |
| `tests/test_cbr_key_rate_source_v1.py` | PR-84 contract, fixed source, XML security, bounded transport and fail-closed errors |
| `tests/test_cbr_key_rate_cache_v1.py` | PR-85 fresh/stale/unavailable contract, single-flight, pruning, eviction and no-silent-stale behavior |
| `tests/test_cbr_key_rate_observability_v1.py` | PR-86 source/cache event mapping, payload exclusions, latency/type guards and no-write surface |
| `tests/test_cbr_key_rate_alert_policy_v1.py` | PR-87 thresholds, firing, cooldown, recovery, concurrency, privacy and no-write surface |
| `tests/test_cbr_key_rate_alert_policy_retention_v1.py` | PR-87 pending retention and active-state cooldown preservation |
| `tests/test_cbr_key_rate_alert_contract_exports_v1.py` | PR-87 public package export compatibility |
| `tests/test_cbr_key_rate_operations_lifecycle_v1.py` | PR-88 event/evaluation/evidence ordering, sinks, concurrency, retention and privacy |
| `tests/test_moex_iss_quote_source_v1.py` | PR-89 contracts, fixed source, JSON/identity/time validation, bounded transport and safety flags |
| `tests/test_moex_iss_quote_contract_exports_v1.py` | PR-89 versioned contract and market-package export compatibility |
| `tests/test_moex_iss_quote_cache_v1.py` | PR-90 cache contract, two-clock freshness, single-flight, stale policy, eviction and safety |
| `tests/test_moex_iss_quote_cache_exports_v1.py` | PR-90 versioned cache-contract and market-package export compatibility |
| `tests/test_moex_iss_quote_observability_v1.py` | PR-91 source/cache mapping, safe metrics, redacted errors and no-write surface |
| `tests/test_moex_iss_quote_observability_privacy_v1.py` | PR-91 serialization exclusions for price, identity and upstream payload |
| `tests/test_moex_iss_quote_observability_exports_v1.py` | PR-91 observability package export compatibility |
| `tests/test_moex_iss_quote_alert_policy_v1.py` | PR-92 canonical gate, global thresholds, cooldown, recovery, retention, concurrency and privacy |
| `tests/test_moex_iss_quote_alert_policy_exports_v1.py` | PR-92 versioned contract and observability-package export compatibility |
| `tests/test_portfolio_market_snapshot.py` | Рыночная оценка портфеля |
| `tests/test_portfolio_analytics.py` | Структура и концентрация |
| `tests/test_cash_liquidity.py` | Деньги и лимиты |
| `tests/test_purchase_capacity*.py` | Purchase preview и арифметическая целостность |
| `tests/test_operations_analytics.py` | Операции и cash-flow reconciliation |
| `tests/test_broker_report*.py` | Брокерский отчёт, reconciliation и async integrity |
| `tests/test_no_telegram_runtime.py` | Запрет retired Telegram runtime |
| `tests/test_ci_security_baseline.py` | Hash locks, Action SHA pins и secret-report policy |
| `tests/test_versioned_data_contracts_v1.py` | Versioning, Decimal JSON, provenance, masking и strict validation |

## Project memory and architecture

| Файл | Назначение |
|---|---|
| `AGENTS.md` | Обязательные правила работы |
| `docs/master-plan/` | Исходная спецификация v9, поисковая копия и приоритет источников |
| `knowledge/00_PROJECT_MASTER_CONTEXT.md` | Полный стратегический контекст и roadmap |
| `knowledge/16_CURRENT_PROGRAM_STATUS.md` | Фактическая вершина программы и следующий пакет |
| `knowledge/09_MARKET_DATA_AND_BUYING_POWER.txt` | Market, macro source/cache и buying-power semantics |
| `knowledge/10_OPERATIONS_ANALYTICS_AND_RECONCILIATION.txt` | Operations semantics |
| `knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt` | Broker-report async semantics |
| `knowledge/12_TELEGRAM_RETIREMENT.txt` | Telegram retirement decision |
| `knowledge/13_COMMUNICATION_STYLE_2026.txt` | Active communication profile |
| `knowledge/14_CI_SECURITY_BASELINE.txt` | Reproducible CI and security gates |
| `knowledge/15_VERSIONED_DATA_CONTRACTS.txt` | Versioned contracts and data-quality profiles |
| `docs/architecture/FINAL_DECISION_REVIEW_AUTHENTICATED_OWNER_INSTALLATION_V1.md` | PR-83 authenticated installation lifecycle |
| `docs/architecture/CBR_KEY_RATE_SOURCE_V1.md` | PR-84 official source, parser and transport security boundary |
| `docs/architecture/CBR_KEY_RATE_CACHE_V1.md` | PR-85 exact-range cache and explicit freshness/display policy |
| `docs/architecture/CBR_KEY_RATE_OBSERVABILITY_V1.md` | PR-86 allowlisted telemetry without key-rate or upstream payload |
| `docs/architecture/CBR_KEY_RATE_ALERT_POLICY_V1.md` | PR-87 bounded alert state, deduplication, cooldown and recovery policy |
| `docs/architecture/CBR_KEY_RATE_OPERATIONS_LIFECYCLE_V1.md` | PR-88 deterministic internal composition and bounded operator evidence |
| `docs/architecture/MOEX_ISS_TQBR_QUOTE_SOURCE_V1.md` | PR-89 fixed TQBR source, public-feed limitations and fail-closed parser/transport boundary |
| `docs/architecture/MOEX_ISS_TQBR_QUOTE_CACHE_V1.md` | PR-90 exact identity cache, two-clock freshness and no-silent-stale policy |
| `docs/architecture/MOEX_ISS_TQBR_QUOTE_OBSERVABILITY_V1.md` | PR-91 pure status telemetry without price, SECID, account or upstream payload |
| `docs/architecture/MOEX_ISS_TQBR_QUOTE_ALERT_POLICY_V1.md` | PR-92 global operational alert state without financial thresholds or external transport |
| `gpt/MY_GPT_SETUP_RUNBOOK.md` | Точная настройка ChatGPT → My GPTs, Actions, Preview и rollback |
| `docs/operations/RELEASE_CHECKLIST.md` | Pre-merge, production and evidence checklist |

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
| `scripts/check_repository_layout.py` | Layout, master-plan, retired paths и broker-write guards |
| `scripts/check_ci_security_baseline.py` | Dependency hashes, Action pins, gates и secret report |

## Правило актуальности

При добавлении, переименовании или удалении ключевого файла обновите этот индекс
в том же Pull Request. `scripts/check_repository_layout.py` контролирует
обязательный набор.
