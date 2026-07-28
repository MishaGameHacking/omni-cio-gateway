# Omni-CIO Control Center

Приватная read-only система инвестиционной аналитики. Поддерживаемый
пользовательский интерфейс находится в Custom GPT внутри ChatGPT:

```text
Custom GPT ── Omni-CIO Gateway (`app:app`) ── T-Invest API
```

## Текущее состояние

- System release: **v4.1.0 ChatGPT-only Runtime**.
- Gateway API component: **v3.9.1 Broker Report Async Integrity**.
- Custom GPT communication profile: **Modern Financial Sage — 2026**.
- Gateway production entrypoint: `app:app`.
- `trading_methods=false`.
- Создание, отправка, замена и отмена заявок запрещены.
- Telegram Companion выведен из эксплуатации; его package, Blueprint,
  webhook и активная конфигурация отсутствуют.

## Начать работу

Новый чат, Codex, Copilot или IDE должны прочитать:

1. [`AGENTS.md`](AGENTS.md)
2. [`docs/README.md`](docs/README.md)
3. [`knowledge/00_PROJECT_MASTER_CONTEXT.md`](knowledge/00_PROJECT_MASTER_CONTEXT.md)
4. [`gpt/INSTRUCTIONS.md`](gpt/INSTRUCTIONS.md)
5. [`gpt/ACTIONS_CATALOG.md`](gpt/ACTIONS_CATALOG.md)
6. профильный файл из [`knowledge/`](knowledge/)

Готовый стартовый запрос: [`gpt/NEW_CHAT_PROMPT.md`](gpt/NEW_CHAT_PROMPT.md).

## Карта репозитория

```text
app.py + runtime modules             Omni-CIO Gateway
broker_report_reconciliation/        официальный отчёт и сверка
tests/                               unit, endpoint, OpenAPI, Regression Shield
knowledge/                           строгие правила предметной области
gpt/                                 переносимая конфигурация Custom GPT
docs/architecture/                   архитектура и карта файлов
docs/operations/                     deploy и release runbooks
docs/inventory/                      реестр GitHub и внешних активов
scripts/                             безопасные локальные проверки
.github/                             CI, CODEOWNERS, PR и Issue templates
```

Полная схема: [`docs/architecture/REPOSITORY_STRUCTURE.md`](docs/architecture/REPOSITORY_STRUCTURE.md).

## Custom GPT: современный стиль 2026

Канонический файл [`gpt/INSTRUCTIONS.md`](gpt/INSTRUCTIONS.md) задаёт единый стиль анализа и публикаций:

- главный вывод в первых предложениях;
- короткие абзацы без банковского канцелярита;
- перевод сложных терминов на человеческий язык;
- разделение факта, вывода и возможного сценария;
- понятная шкала риска;
- умеренный мат только как эмоциональный акцент, а не замена фактам;
- формат денег ru-RU для рублей и сохранение исходной валюты;
- мобильный формат публикаций с датой и источниками;
- сохранение GET-only и `trading_methods=false`.

Профиль знаний: [`knowledge/13_COMMUNICATION_STYLE_2026.txt`](knowledge/13_COMMUNICATION_STYLE_2026.txt).

Важно: GitHub хранит канонические инструкции, но не может автоматически заменить поле Instructions в GPT Editor. После изменения этого файла владелец вручную вставляет его полный текст в GPT Editor и нажимает **Update**. Повторный импорт OpenAPI не требуется, если контракт Actions не менялся.

## ChatGPT-only runtime

Omni-CIO больше не содержит Telegram runtime. Полезная финансовая логика
не потеряна: она изначально находилась в Gateway, а удалённые модули
обслуживали только Telegram transport, команды и форматирование.

После merge внешний Telegram service и webhook нужно удалить вручную по
[`docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md`](docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md).
Удалять или изменять основной service `omni-cio-gateway` не нужно.

## Что хранится в GitHub

- весь backend-код gateway;
- OpenAPI-контракт и тесты;
- Gateway Render Blueprint;
- правила безопасности и разработки;
- канонические инструкции Custom GPT;
- современный профиль общения и публикаций;
- каталог Actions;
- проектная память и дорожная карта;
- runbooks и changelog.

## Что намеренно не хранится

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY`;
- полный номер брокерского счёта;
- реальные брокерские отчёты и операции пользователя;
- Render secrets и секретный GPT Bearer key.

Полный реестр: [`docs/inventory/PROJECT_ASSETS.md`](docs/inventory/PROJECT_ASSETS.md).

## Основные документы

- [`AGENTS.md`](AGENTS.md) — обязательные правила.
- [`CHANGELOG.md`](CHANGELOG.md) — история релизов.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — рабочий процесс.
- [`SECURITY.md`](SECURITY.md) — политика безопасности.
- [`docs/architecture/SYSTEM_OVERVIEW.md`](docs/architecture/SYSTEM_OVERVIEW.md) — архитектура.
- [`docs/operations/DEPLOYMENT_RUNBOOK.md`](docs/operations/DEPLOYMENT_RUNBOOK.md) — gateway deployment.
- [`docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md`](docs/operations/TELEGRAM_REMOVAL_RUNBOOK.md) — очистка выведенного Telegram service.
- [`knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt`](knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt) — асинхронный отчёт.
- [`knowledge/12_TELEGRAM_RETIREMENT.txt`](knowledge/12_TELEGRAM_RETIREMENT.txt) — запрет возврата Telegram runtime без нового ADR.
- [`knowledge/13_COMMUNICATION_STYLE_2026.txt`](knowledge/13_COMMUNICATION_STYLE_2026.txt) — современная речь и публикации.

## Локальный запуск gateway

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export TINVEST_TOKEN="..."
export GATEWAY_API_KEY="..."
export SSL_TBANK_VERIFY="True"
uvicorn app:app --reload
```

## Проверки

```bash
python scripts/check_repository_layout.py
python -m compileall -q app.py app_v371.py app_v360.py main.py \
  portfolio_market.py portfolio_analytics.py cash_liquidity.py \
  purchase_capacity.py purchase_capacity_integrity.py \
  operations_analytics.py broker_report_reconciliation tests scripts
python -m pytest -q
```

Regression Shield контролирует стабильный `app:app`, отсутствие Telegram
runtime/configuration, отсутствие торговых функций и
`trading_methods=false`.

## Деплой

- Gateway: [`render.yaml`](render.yaml), entrypoint `app:app`.

## Важная граница проекта

Исходный frontend существующего сайта Omni-CIO пока не закреплён за этим репозиторием. Не создавайте дубликат сайта.
