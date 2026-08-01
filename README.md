# Omni-CIO Control Center

Приватная read-only система инвестиционной аналитики для российского рынка.
Поддерживаемый пользовательский интерфейс находится в Custom GPT внутри
ChatGPT:

```text
Custom GPT ── Omni-CIO Gateway (`app:app`) ── T-Invest API
                         │
                         └── official market, macro and rating sources
```

## Текущее состояние

- System release: **v4.1.0 ChatGPT-only Runtime**.
- Gateway API component: **v3.10.0 Final Decision Review GET Route**.
- Фактическая слитая функциональная вершина на 2026-08-01: **PR-104**.
- Последний подтверждённый `main` merge: `34708f82d20e054bdd420ac1e9993c6d117e12d7`.
- Gateway production entrypoint: `app:app`.
- User-facing surface: exactly 14 GET Actions.
- `trading_methods=false`.
- Создание, отправка, замена и отмена заявок запрещены.
- Вывод, перевод денег и перевод ценных бумаг не реализуются.
- Telegram Companion выведен из эксплуатации; package, Blueprint, webhook и
  активная конфигурация отсутствуют.
- Functional roadmap временно находится в audit hold до закрытия PR #130,
  документационных расхождений, warning debt и dependency queue review.

Оперативное состояние и следующий безопасный пакет:
[`knowledge/16_CURRENT_PROGRAM_STATUS.md`](knowledge/16_CURRENT_PROGRAM_STATUS.md).

Аудит 2026-08-01:
[`docs/audits/PROJECT_AUDIT_2026-08-01.md`](docs/audits/PROJECT_AUDIT_2026-08-01.md).

## Что уже реализовано

### Gateway and portfolio

- connection and health;
- portfolio snapshots and instrument enrichment;
- portfolio market snapshot and analytics;
- cash and liquidity diagnostics;
- purchase-capacity preview and integrity;
- operations history, analytics and cash-flow reconciliation;
- official T-Invest broker-report generation and reconciliation;
- private read-only final-decision-review retrieval;
- fail-closed quality, risk, shadow, paper and preview controls.

### Official sources

- Bank of Russia key-rate source, exact cache, safe observability, global alert
  policy and deterministic evidence lifecycle;
- MOEX ISS TQBR quote source, exact cache, safe observability, global alert
  policy and deterministic evidence lifecycle;
- separate ACRA issuer-rating source, cache, observability, alert and evidence;
- separate Expert RA issuer-rating source, cache, observability, alert and
  evidence;
- separate NCR issuer-rating source.

Agency scales and subject identities are not merged through a generic adapter.
These packages do not create routes, startup network calls or trading authority
unless a separately reviewed contract explicitly says otherwise.

## Safety invariants

- all user-facing Gateway Actions are GET-only;
- `trading_methods=false` is verified by Regression Shield;
- `app:app` remains the stable Render entrypoint;
- no order, stop-order, cancellation, transfer or withdrawal operation is
  published or allowed;
- account identifiers are masked;
- secrets and real brokerage payloads are not stored in GitHub;
- currencies are not combined without verified FX and timestamp;
- monetary calculations use exact decimal logic;
- stale, partial, truncated or contradictory data fail closed;
- no test calls real Render or T-Invest production endpoints;
- each package uses a separate branch and Pull Request;
- squash merge is allowed only after exact-head Regression Shield.

Canonical rules: [`AGENTS.md`](AGENTS.md).

## Начать работу

Новый чат, Codex, Copilot или IDE должны прочитать:

1. [`AGENTS.md`](AGENTS.md)
2. [`README.md`](README.md)
3. [`docs/README.md`](docs/README.md)
4. [`docs/master-plan/README.md`](docs/master-plan/README.md)
5. [`docs/master-plan/OMNI_CIO_MASTER_PROMPT_V9.txt`](docs/master-plan/OMNI_CIO_MASTER_PROMPT_V9.txt)
6. [`knowledge/00_PROJECT_MASTER_CONTEXT.md`](knowledge/00_PROJECT_MASTER_CONTEXT.md)
7. [`knowledge/16_CURRENT_PROGRAM_STATUS.md`](knowledge/16_CURRENT_PROGRAM_STATUS.md)
8. [`gpt/INSTRUCTIONS.md`](gpt/INSTRUCTIONS.md)
9. [`gpt/ACTIONS_CATALOG.md`](gpt/ACTIONS_CATALOG.md)
10. профильный файл из [`knowledge/`](knowledge/)
11. current `main`, open PRs, issue #27 and latest GitHub Actions

Готовый стартовый запрос: [`gpt/NEW_CHAT_PROMPT.md`](gpt/NEW_CHAT_PROMPT.md).

Старая переписка или временный номер PR не заменяют фактический `main`.

## Карта репозитория

```text
app.py + runtime modules             Omni-CIO Gateway
omni_cio/contracts/                  versioned financial contracts
omni_cio/adapters/                   broker/legacy adapters
omni_cio/quality/                    validation and quality gates
omni_cio/market/                     market, macro and rating sources
omni_cio/analytics/                  portfolio and financial analytics
omni_cio/risk/                       risk controls and scenarios
omni_cio/decision/                   decision and final-review logic
omni_cio/observability/              allowlisted structured telemetry
omni_cio/release/                    release and acceptance controls
broker_report_reconciliation/        official report reconciliation
tests/                               unit, endpoint, OpenAPI and policy tests
knowledge/                           domain rules and project memory
gpt/                                 portable Custom GPT configuration
docs/master-plan/                    owner specification
docs/architecture/                   architecture and contracts
docs/operations/                     deploy, acceptance and recovery runbooks
docs/audits/                         dated repository audits
docs/inventory/                      GitHub and external asset inventory
scripts/                             local and CI safety checks
.github/                             workflows, templates and governance
```

Полная схема:
[`docs/architecture/REPOSITORY_STRUCTURE.md`](docs/architecture/REPOSITORY_STRUCTURE.md).

## Custom GPT

Canonical GPT instructions and Action catalog live in `gpt/`.

- GitHub does not update GPT Editor automatically.
- Bearer key and publication state stay outside GitHub.
- OpenAPI must be re-imported only after a real contract change.
- Authenticated Preview and complete Action-list inspection are required.
- Current official OpenAI documentation must be rechecked at acceptance time.

Setup and rollback:
[`gpt/MY_GPT_SETUP_RUNBOOK.md`](gpt/MY_GPT_SETUP_RUNBOOK.md).

## ChatGPT-only runtime

Omni-CIO no longer contains Telegram runtime. The removed modules were transport
and formatting code; supported financial logic remains in Gateway/domain
modules.

External cleanup of the old Telegram service, webhook and token was completed
by the owner on 2026-07-28. History and controls:
[`docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md`](docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md).

Returning Telegram requires a separate ADR, threat model, deployment contract,
tests and explicit owner approval.

## Dependency policy

Human-edited direct constraints:

- `requirements.in`;
- `requirements-dev.in`.

Generated locks:

- `requirements.txt`;
- `requirements-dev.txt`.

Rules:

- exact versions and SHA-256 hashes;
- install with `--require-hashes`;
- do not edit lock files manually;
- dependency upgrades use dedicated compatibility PRs;
- inspect release notes and all transitive changes;
- regenerate locks and run full Regression Shield;
- GitHub Actions remain pinned to full commit SHAs;
- a historical green Dependabot icon is not enough after `main` changes.

Current direct pins and open upgrade queue are recorded in
[`knowledge/16_CURRENT_PROGRAM_STATUS.md`](knowledge/16_CURRENT_PROGRAM_STATUS.md).

## Локальный запуск Gateway

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.txt
export TINVEST_TOKEN="..."
export GATEWAY_API_KEY="..."
export SSL_TBANK_VERIFY="True"
uvicorn app:app --reload
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --require-hashes -r requirements-dev.txt
$env:TINVEST_TOKEN = "..."
$env:GATEWAY_API_KEY = "..."
$env:SSL_TBANK_VERIFY = "True"
uvicorn app:app --reload
```

Never commit real tokens or paste them into issues, PRs, logs or chat.

## Обязательные проверки

```bash
python scripts/check_ci_security_baseline.py
python scripts/check_repository_layout.py
python -m ruff check .
python -m ruff format --check scripts tests/test_ci_security_baseline.py
python -m mypy
python -m compileall -q app.py app_v371.py app_v360.py main.py \
  portfolio_market.py portfolio_analytics.py cash_liquidity.py \
  purchase_capacity.py purchase_capacity_integrity.py \
  operations_analytics.py broker_report_reconciliation tests scripts
python -m pytest -q --cov=app --cov=main \
  --cov=portfolio_market --cov=portfolio_analytics \
  --cov=cash_liquidity --cov=purchase_capacity \
  --cov=purchase_capacity_integrity --cov=operations_analytics \
  --cov=sdk_order_compat --cov=broker_report_reconciliation \
  --cov-branch --cov-fail-under=60
python -m pip_audit --require-hashes --disable-pip --strict \
  --vulnerability-service osv --progress-spinner off \
  -r requirements.txt
python -m bandit -q -lll -iii -r . \
  -x tests,.venv,venv,htmlcov,broker_report_reconciliation/_parts \
  --exclude "./broker_report_reconciliation/__init__.py"
python scripts/scan_tracked_secrets.py
```

GitHub Regression Shield is the required source of merge evidence. Focused
local tests do not replace the complete workflow.

## Production acceptance

Green CI does not prove external production state. Required evidence remains:

1. Render source commit verification;
2. cache-busted `/health`;
3. auth-negative production check;
4. exact-route positive production check;
5. GPT Editor schema import;
6. authenticated Preview;
7. complete Action-list inspection;
8. rollback restore.

Runbooks:

- [`docs/operations/DEPLOYMENT_RUNBOOK.md`](docs/operations/DEPLOYMENT_RUNBOOK.md)
- [`docs/operations/RELEASE_CHECKLIST.md`](docs/operations/RELEASE_CHECKLIST.md)
- [`docs/operations/LIVE_READ_ONLY_ACCEPTANCE.md`](docs/operations/LIVE_READ_ONLY_ACCEPTANCE.md)

## Remaining program blocks

- close the 2026-08-01 audit hold and PR #130;
- classify and remove warning debt;
- review open dependency PRs against current `main`;
- add remaining official sources only through separate fixed contracts;
- production-grade news and corporate-event ingestion;
- external versioned RAG with freshness and citations;
- exact production frontend/owner binding;
- safe SberInvestments HTML import, archive and comparison;
- broader monitoring, rollback and incident operations;
- real Render/Gateway/GPT acceptance.

Any live-trading work is a separate owner-approved admission program. Shadow,
paper, preview and final review do not authorize execution.

## Основные документы

- [`AGENTS.md`](AGENTS.md) — mandatory engineering and safety rules.
- [`knowledge/00_PROJECT_MASTER_CONTEXT.md`](knowledge/00_PROJECT_MASTER_CONTEXT.md) — durable project context.
- [`knowledge/16_CURRENT_PROGRAM_STATUS.md`](knowledge/16_CURRENT_PROGRAM_STATUS.md) — current merged top and audit gates.
- [`docs/audits/PROJECT_AUDIT_2026-08-01.md`](docs/audits/PROJECT_AUDIT_2026-08-01.md) — latest repository-wide audit.
- [`CHANGELOG.md`](CHANGELOG.md) — release history.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contribution workflow.
- [`SECURITY.md`](SECURITY.md) — security policy.
- [`docs/master-plan/README.md`](docs/master-plan/README.md) — owner specification hierarchy.
- [`docs/architecture/SYSTEM_OVERVIEW.md`](docs/architecture/SYSTEM_OVERVIEW.md) — system architecture.
- [`docs/inventory/PROJECT_ASSETS.md`](docs/inventory/PROJECT_ASSETS.md) — repository and external assets.
- [`gpt/MY_GPT_SETUP_RUNBOOK.md`](gpt/MY_GPT_SETUP_RUNBOOK.md) — GPT setup and rollback.
