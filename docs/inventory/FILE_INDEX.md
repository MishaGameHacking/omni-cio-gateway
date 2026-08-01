# Индекс файлов проекта

Этот файл перечисляет активные runtime, contracts, tests, architecture,
operations and audit assets в текущей ветке. Код в актуальном `main` остаётся
окончательным источником истины.

## Gateway runtime

| Файл | Назначение |
|---|---|
| `app.py` | Стабильный production entrypoint `app:app`, OpenAPI and release wrapper |
| `app_v371.py` / `app_v360.py` | Архивные совместимые wrappers |
| `main.py` | Историческое FastAPI-ядро, auth and base read-only routes |
| `portfolio_market.py` | Portfolio Market Snapshot |
| `portfolio_analytics.py` | Portfolio Analytics Core |
| `cash_liquidity.py` | Cash & Liquidity Diagnostics |
| `purchase_capacity.py` / `purchase_capacity_integrity.py` | Purchase preview and integrity checks |
| `operations_analytics.py` | Operations Analytics and Cash Flow Reconciliation |
| `broker_report_reconciliation/` | Official broker report, pagination and reconciliation |

## Versioned contracts

| Файл/папка | Назначение |
|---|---|
| `omni_cio/contracts/v1/` | Strict versioned Pydantic contracts |
| `omni_cio/contracts/v1/macro.py` | CBR source/cache contracts |
| `omni_cio/contracts/v1/alerting.py` | CBR alert/evidence contracts |
| `omni_cio/contracts/v1/moex.py` | MOEX source/cache contracts |
| `omni_cio/contracts/v1/moex_alerting.py` | MOEX alert/evidence contracts |
| `omni_cio/contracts/v1/ratings.py` | ACRA issuer-action and cache contracts |
| `omni_cio/contracts/v1/acra_alerting.py` | ACRA alert/evidence contracts |
| `omni_cio/contracts/v1/expert_ra_ratings.py` | Expert RA source/cache contracts |
| `omni_cio/contracts/v1/expert_ra_alerting.py` | Expert RA alert/evidence contracts |
| `omni_cio/contracts/v1/ncr_ratings.py` | NCR issuer-action and source snapshot contracts |

## Market and macro runtime

| Файл/маска | Назначение |
|---|---|
| `omni_cio/market/cbr_key_rate_v1.py` | Fixed Bank of Russia source |
| `omni_cio/market/cbr_key_rate_cache_v1.py` | Exact-range CBR cache |
| `omni_cio/market/moex_iss_quote_v1.py` | Fixed public MOEX ISS TQBR source |
| `omni_cio/market/moex_iss_quote_cache_v1.py` | Exact TQBR+SECID cache |
| `omni_cio/market/acra_rating_actions_v1.py` | Fixed ACRA issuer-rating source |
| `omni_cio/market/acra_rating_actions_cache_v1.py` | ACRA source cache |
| `omni_cio/market/expert_ra_rating_actions_v1.py` | Fixed Expert RA issuer-rating source |
| `omni_cio/market/expert_ra_rating_actions_cache_v1.py` | Expert RA source cache |
| `omni_cio/market/ncr_rating_actions_v1.py` | Fixed NCR issuer-rating source |
| `omni_cio/market/` | Capacity, bond, equity, fund and technical-analysis modules |

## Observability and operations evidence

| Файл/маска | Назначение |
|---|---|
| `omni_cio/observability/safe_events_v1.py` | Allowlisted structured event builder/emitter |
| `omni_cio/observability/cbr_key_rate_*` | CBR events, alert policy and evidence lifecycle |
| `omni_cio/observability/moex_iss_quote_*` | MOEX events, alert policy and evidence lifecycle |
| `omni_cio/observability/acra_rating_actions_*` | ACRA events, alert policy and evidence lifecycle |
| `omni_cio/observability/expert_ra_rating_actions_*` | Expert RA events, alert policy and evidence lifecycle |

NCR currently has a fixed source only. Any NCR cache, telemetry, alert or
evidence package must be added separately.

## Final-review release chain

`omni_cio/release/` contains the private read-only final-review chain:
trusted publication, compact route, acceptance evidence, workflow bridge,
source acquisition, calculator handoff, provider registry, approved owner
composition/installation, authenticated context, typed snapshots and bounded
redacted evidence.

Key entrypoints:

| Файл | Назначение |
|---|---|
| `omni_cio/release/final_decision_review_route_v1.py` | Private GET route boundary |
| `omni_cio/release/final_decision_review_acceptance_v1.py` | Offline production acceptance collector |
| `omni_cio/release/final_decision_review_production_registration_v1.py` | Lazy runtime registration |
| `omni_cio/release/final_decision_review_authenticated_owner_installation_v1.py` | Post-auth snapshot selection and evidence |

## Configuration and automation

| Файл | Назначение |
|---|---|
| `render.yaml` | Единственный Gateway Render contract |
| `requirements.in` / `requirements.txt` | Hash-locked runtime dependencies |
| `requirements-dev.in` / `requirements-dev.txt` | Hash-locked development dependencies |
| `pyproject.toml` | Ruff, mypy, pytest/coverage and Bandit baseline |
| `.env.example` | Только имена переменных и safe placeholders |
| `.github/workflows/regression-shield.yml` | Blocking quality/contracts/coverage/security CI |
| `.github/dependabot.yml` | Dependency update policy |
| `.github/CODEOWNERS` | Ownership |
| `.github/pull_request_template.md` | Pull Request Definition of Done |
| `scripts/check_repository_layout.py` | Layout and broker-write guards |
| `scripts/check_ci_security_baseline.py` | Locks, Action pins and security policy |
| `scripts/scan_tracked_secrets.py` | Tracked-secret scan |

Draft PR #130 proposes a Windows runner diagnostic, tests and runbook. Those
files are not active `main` assets until that PR passes fresh CI and merges.

## Tests

| Файл/маска | Область |
|---|---|
| `tests/test_regression_shield.py` | Entrypoint, OpenAPI, auth and read-only invariants |
| `tests/test_final_decision_review_*` | Final-review release chain |
| `tests/test_cbr_key_rate_*` | CBR source/cache/telemetry/alert/evidence |
| `tests/test_moex_iss_quote_*` | MOEX source/cache/telemetry/alert/evidence |
| `tests/test_acra_rating_actions_*` | ACRA source/cache/telemetry/alert/evidence |
| `tests/test_expert_ra_*` | Expert RA source/cache/telemetry/alert/evidence |
| `tests/test_ncr_rating_actions_*` | NCR source contracts, parser and transport |
| `tests/test_portfolio_*` | Portfolio market and analytics |
| `tests/test_purchase_capacity*.py` | Purchase preview integrity |
| `tests/test_operations_analytics.py` | Operations and cash-flow reconciliation |
| `tests/test_broker_report*.py` | Broker report and async integrity |
| `tests/test_ci_security_baseline.py` | Dependency/security baseline |
| `tests/test_no_telegram_runtime.py` | Retired Telegram runtime guard |

## Architecture

| Файл/маска | Назначение |
|---|---|
| `docs/architecture/SYSTEM_OVERVIEW.md` | System overview |
| `docs/architecture/REPOSITORY_STRUCTURE.md` | Repository structure |
| `docs/architecture/DECISIONS.md` | Architecture decisions |
| `docs/architecture/FINAL_DECISION_REVIEW_*` | Final-review contracts and lifecycle |
| `docs/architecture/CBR_KEY_RATE_*` | CBR source/cache/operations chain |
| `docs/architecture/MOEX_ISS_TQBR_QUOTE_*` | MOEX source/cache/operations chain |
| `docs/architecture/ACRA_*` | ACRA source/cache/operations chain |
| `docs/architecture/EXPERT_RA_*` | Expert RA source/cache/operations chain |
| `docs/architecture/NCR_ISSUER_RATING_ACTION_SOURCE_V1.md` | NCR fixed source boundary |

## Operations

| Файл | Назначение |
|---|---|
| `docs/operations/DEPLOYMENT_RUNBOOK.md` | Render/Gateway deployment |
| `docs/operations/RELEASE_CHECKLIST.md` | Merge and production evidence checklist |
| `docs/operations/LIVE_READ_ONLY_ACCEPTANCE.md` | External Render/Gateway/GPT cases |
| `docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md` | Retired Telegram cleanup history |

## Project memory and audits

| Файл | Назначение |
|---|---|
| `AGENTS.md` | Mandatory project rules |
| `README.md` | Current overview and local workflow |
| `knowledge/00_PROJECT_MASTER_CONTEXT.md` | Durable architecture and safety context |
| `knowledge/09_MARKET_DATA_AND_BUYING_POWER.txt` | Market/macro semantics |
| `knowledge/14_CI_SECURITY_BASELINE.txt` | CI/security baseline |
| `knowledge/15_VERSIONED_DATA_CONTRACTS.txt` | Versioned contract rules |
| `knowledge/16_CURRENT_PROGRAM_STATUS.md` | Current merged top, audit gates and next package |
| `docs/audits/PROJECT_AUDIT_2026-08-01.md` | Repository-wide audit, defects, dependency and acceptance classification |
| `docs/inventory/PROJECT_ASSETS.md` | GitHub and external assets |
| `docs/inventory/FILE_INDEX.md` | This file |

## Custom GPT

| Файл/папка | Назначение |
|---|---|
| `gpt/INSTRUCTIONS.md` | Canonical assistant behavior |
| `gpt/ACTIONS_CATALOG.md` | Exact Action catalog |
| `gpt/MY_GPT_SETUP_RUNBOOK.md` | Setup, Preview and rollback |
| `gpt/NEW_CHAT_PROMPT.md` | Context bootstrap |
| `gpt/` | Remaining portable GPT configuration assets |

## Правило актуальности

При добавлении, переименовании или удалении ключевого runtime, contract, test,
architecture, operations or audit file этот индекс обновляется в том же Pull
Request.

Не хранить в GitHub secrets, реальные отчёты, full account identifiers, raw
CBR XML, MOEX JSON, rating-agency HTML, upstream body/exception text,
process-local cache/alert/evidence state, runner credentials or registration
tokens.
