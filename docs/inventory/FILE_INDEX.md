# Индекс файлов проекта

Этот файл перечисляет активные runtime, contracts, tests, architecture и
operations assets. Код в `main` остаётся окончательным источником истины.

## Gateway runtime

| Файл | Назначение |
|---|---|
| `app.py` | Стабильный production entrypoint `app:app`, OpenAPI и release wrapper |
| `app_v371.py` / `app_v360.py` | Архивные совместимые wrappers |
| `main.py` | Историческое FastAPI-ядро, auth и базовые read-only routes |
| `portfolio_market.py` | Portfolio Market Snapshot |
| `portfolio_analytics.py` | Portfolio Analytics Core |
| `cash_liquidity.py` | Cash & Liquidity Diagnostics |
| `purchase_capacity.py` / `purchase_capacity_integrity.py` | Purchase preview и integrity checks |
| `operations_analytics.py` | Operations Analytics & Cash Flow Reconciliation |
| `broker_report_reconciliation/` | Официальный broker report, pagination и reconciliation |

## Versioned contracts

| Файл | Назначение |
|---|---|
| `omni_cio/contracts/v1/` | Strict immutable Pydantic contracts v1 |
| `omni_cio/contracts/v1/macro.py` | PR-84/85 CBR source/cache contracts |
| `omni_cio/contracts/v1/alerting.py` | PR-87/88 CBR alert/evidence contracts |
| `omni_cio/contracts/v1/moex.py` | PR-89/90 MOEX source/cache contracts |
| `omni_cio/contracts/v1/moex_alerting.py` | PR-92/93 global MOEX alert/evidence contracts |
| `omni_cio/contracts/v1/ratings.py` | PR-94/95 ACRA issuer actions and explicit source/cache contracts |
| `omni_cio/contracts/v1/acra_alerting.py` | PR-97 global operational ACRA alert policy/evaluation contracts |

## Market and macro runtime

| Файл | Назначение |
|---|---|
| `omni_cio/market/cbr_key_rate_v1.py` | PR-84 fixed Bank of Russia source and protected XML parsing |
| `omni_cio/market/cbr_key_rate_cache_v1.py` | PR-85 exact-range fresh/stale/unavailable cache |
| `omni_cio/market/moex_iss_quote_v1.py` | PR-89 fixed public MOEX ISS TQBR source |
| `omni_cio/market/moex_iss_quote_cache_v1.py` | PR-90 exact TQBR+SECID cache and no-silent-stale policy |
| `omni_cio/market/acra_rating_actions_v1.py` | PR-94 fixed official issuer-level ACRA source |
| `omni_cio/market/acra_rating_actions_cache_v1.py` | PR-95 fixed-source single-flight ACRA cache |
| `omni_cio/market/` | Existing capacity, bond, equity, fund and technical analysis |

## Observability and operations evidence

| Файл | Назначение |
|---|---|
| `omni_cio/observability/safe_events_v1.py` | Allowlisted structured event builder/emitter |
| `omni_cio/observability/cbr_key_rate_events_v1.py` | PR-86 CBR source/cache status telemetry |
| `omni_cio/observability/cbr_key_rate_alert_policy_v1.py` | PR-87 bounded CBR alert policy |
| `omni_cio/observability/cbr_key_rate_operations_lifecycle_v1.py` | PR-88 fired/recovered evidence lifecycle |
| `omni_cio/observability/moex_iss_quote_events_v1.py` | PR-91 MOEX telemetry without price or SECID |
| `omni_cio/observability/moex_iss_quote_alert_policy_v1.py` | PR-92 global MOEX alert state machine |
| `omni_cio/observability/moex_iss_quote_operations_lifecycle_v1.py` | PR-93 global fired/recovered evidence lifecycle |
| `omni_cio/observability/acra_rating_actions_events_v1.py` | PR-96 pure ACRA source/cache telemetry without issuer/rating content |
| `omni_cio/observability/acra_rating_actions_alert_policy_v1.py` | PR-97 strict global ACRA operational alert evaluator |

## Final-review release chain

`omni_cio/release/` contains the PR-50…PR-83 private read-only final-review
chain: trusted publication, compact route, acceptance evidence, workflow bridge,
source acquisition, calculator handoff, provider registry, approved owner
composition/installation, authenticated context, typed snapshots and bounded
redacted evidence. Public registration remains explicit and protected by the
14-GET release contract.

Key entrypoints:

| Файл | Назначение |
|---|---|
| `omni_cio/release/final_decision_review_route_v1.py` | Private GET route boundary |
| `omni_cio/release/final_decision_review_acceptance_v1.py` | Offline eight-case production acceptance collector |
| `omni_cio/release/final_decision_review_production_registration_v1.py` | Lazy runtime registration through PR-83 |
| `omni_cio/release/final_decision_review_authenticated_owner_installation_v1.py` | Post-auth exact snapshot selection and bounded evidence |

## Configuration and automation

| Файл | Назначение |
|---|---|
| `render.yaml` | Единственный Gateway Render contract |
| `requirements.in` / `requirements.txt` | Hash-locked production dependencies |
| `requirements-dev.in` / `requirements-dev.txt` | Hash-locked development dependencies |
| `pyproject.toml` | Ruff, mypy, pytest/coverage и Bandit baseline |
| `.env.example` | Только имена переменных, без секретов |
| `.github/workflows/regression-shield.yml` | Blocking quality/contracts/coverage/security CI |
| `.github/dependabot.yml` | Dependency updates |
| `.github/CODEOWNERS` | Ownership |
| `.github/pull_request_template.md` | Pull Request Definition of Done |
| `scripts/check_repository_layout.py` | Layout и broker-write guards |
| `scripts/check_ci_security_baseline.py` | Locks, Action pins и security policy |

## Tests

| Файл/маска | Область |
|---|---|
| `tests/test_regression_shield.py` | Entrypoint, OpenAPI, auth и read-only invariants |
| `tests/test_final_decision_review_*` | PR-50…PR-83 release chain |
| `tests/test_cbr_key_rate_*` | PR-84…PR-88 source, cache, telemetry, alert и evidence |
| `tests/test_moex_iss_quote_*` | PR-89…PR-93 source, cache, telemetry, alert и evidence |
| `tests/test_acra_rating_actions_source_v1.py` | PR-94 source contracts, parser, transport and safety |
| `tests/test_acra_rating_actions_exports_v1.py` | PR-94 export compatibility |
| `tests/test_acra_rating_actions_cache_v1.py` | PR-95 fresh/stale/unavailable, single-flight and expiry |
| `tests/test_acra_rating_actions_cache_exports_v1.py` | PR-95 cache export compatibility |
| `tests/test_acra_rating_actions_observability_v1.py` | PR-96 mapping, safe metrics, privacy and no-write surface |
| `tests/test_acra_rating_actions_observability_exports_v1.py` | PR-96 observability export compatibility |
| `tests/test_acra_rating_actions_alert_policy_v1.py` | PR-97 canonical gate, thresholds, cooldown, recovery, concurrency and privacy |
| `tests/test_acra_rating_actions_alert_policy_exports_v1.py` | PR-97 contract/runtime export compatibility |
| `tests/test_portfolio_*` | Portfolio market and analytics |
| `tests/test_purchase_capacity*.py` | Purchase preview integrity |
| `tests/test_operations_analytics.py` | Operations and cash-flow reconciliation |
| `tests/test_broker_report*.py` | Broker report and async integrity |
| `tests/test_ci_security_baseline.py` | Dependency/security baseline |
| `tests/test_no_telegram_runtime.py` | Retired Telegram runtime guard |

## Project memory and architecture

| Файл | Назначение |
|---|---|
| `AGENTS.md` | Обязательные правила работы |
| `knowledge/00_PROJECT_MASTER_CONTEXT.md` | Стратегический контекст и roadmap |
| `knowledge/09_MARKET_DATA_AND_BUYING_POWER.txt` | Market/macro semantics |
| `knowledge/14_CI_SECURITY_BASELINE.txt` | CI/security baseline |
| `knowledge/15_VERSIONED_DATA_CONTRACTS.txt` | Versioned contracts rules |
| `knowledge/16_CURRENT_PROGRAM_STATUS.md` | Фактическая вершина и следующий пакет |
| `docs/architecture/ACRA_ISSUER_RATING_ACTION_SOURCE_V1.md` | PR-94 source boundary |
| `docs/architecture/ACRA_ISSUER_RATING_ACTION_CACHE_V1.md` | PR-95 cache/freshness boundary |
| `docs/architecture/ACRA_ISSUER_RATING_ACTION_OBSERVABILITY_V1.md` | PR-96 telemetry/privacy boundary |
| `docs/architecture/ACRA_RATING_ACTIONS_ALERT_POLICY_V1.md` | PR-97 global alert policy and canonical-event gate |
| `docs/architecture/CBR_KEY_RATE_*` | PR-84…PR-88 CBR architecture |
| `docs/architecture/MOEX_ISS_TQBR_QUOTE_*` | PR-89…PR-93 MOEX architecture |
| `gpt/MY_GPT_SETUP_RUNBOOK.md` | Custom GPT setup, Preview and rollback |
| `docs/operations/RELEASE_CHECKLIST.md` | Pre-merge and production evidence checklist |

## Правило актуальности

При добавлении, переименовании или удалении ключевого runtime, contract, test или
architecture file этот индекс обновляется в том же Pull Request. Секреты,
реальные отчёты, account identifiers, raw CBR XML, raw MOEX JSON, raw ACRA HTML и
process-local cache/evidence state в GitHub не хранятся.
