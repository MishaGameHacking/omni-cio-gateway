# Omni-CIO Control Center

Приватная read-only система инвестиционной аналитики. Один GitHub-репозиторий содержит два независимых интерфейса к общему Omni-CIO Gateway:

```text
Custom GPT ──────┐
                 ├── Omni-CIO Gateway ── T-Invest API
Telegram Bot ────┘
```

## Текущее состояние

- System release: **v4.0.1 Telegram Reliability & Friendly Output**.
- Gateway API component: **v3.9.1 Broker Report Async Integrity**.
- Custom GPT communication profile: **Modern Financial Sage — 2026**.
- Gateway production entrypoint: `app:app`.
- Telegram production entrypoint: `telegram_bot.app:app`.
- `trading_methods=false` в обоих интерфейсах.
- Создание, отправка, замена и отмена заявок запрещены.
- Custom GPT и Telegram не делят историю чатов, но используют один gateway и одни правила данных.

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
telegram_bot/                        Telegram Companion v4.0.1
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
- мобильный формат Telegram-постов с датой и источниками;
- сохранение GET-only и `trading_methods=false`.

Профиль знаний: [`knowledge/13_COMMUNICATION_STYLE_2026.txt`](knowledge/13_COMMUNICATION_STYLE_2026.txt).

Важно: GitHub хранит канонические инструкции, но не может автоматически заменить поле Instructions в GPT Editor. После изменения этого файла владелец вручную вставляет его полный текст в GPT Editor и нажимает **Update**. Повторный импорт OpenAPI не требуется, если контракт Actions не менялся.

## Telegram Companion

Telegram-интерфейс работает по предсказуемым командам без OpenAI API:

```text
/help
/status
/health
/connection
/portfolio
/cash
/analytics
/operations [days]
/report
/report_status [task_id]
```

v4.0.1 добавляет:

- краткие русские сводки вместо больших JSON-блоков;
- `/status` для проверки Telegram, Gateway и T-Invest;
- автоматические повторы временно недоступного Gateway;
- уведомление о пробуждении бесплатного Render service;
- безопасное разбиение длинных ответов на части;
- typing indicator как необязательное удобство.

Telegram не пересчитывает и не улучшает финансовые данные: он только выбирает безопасные поля из ответа gateway и показывает их в более удобной форме.

Безопасность:

- отдельный Render web service;
- Telegram webhook с `X-Telegram-Bot-Api-Secret-Token`;
- доступ только для `TELEGRAM_ALLOWED_USER_IDS`;
- только личные чаты;
- дедупликация Telegram `update_id`;
- rate limit;
- gateway вызывается только методом GET с Bearer key;
- повторное маскирование account ID;
- секреты не выводятся в health и сообщения.

Инструкция развёртывания: [`docs/operations/TELEGRAM_COMPANION_RUNBOOK.md`](docs/operations/TELEGRAM_COMPANION_RUNBOOK.md).

Отдельный безопасный Blueprint: [`render.telegram.yaml`](render.telegram.yaml). Он не изменяет существующий gateway service.

## Что хранится в GitHub

- весь backend-код gateway;
- Telegram Companion;
- OpenAPI-контракт и тесты;
- Render Blueprints;
- правила безопасности и разработки;
- канонические инструкции Custom GPT;
- современный профиль общения и публикаций;
- каталог Actions;
- проектная память и дорожная карта;
- runbooks и changelog.

## Что намеренно не хранится

- `TINVEST_TOKEN`;
- `GATEWAY_API_KEY` и `OMNI_GATEWAY_API_KEY`;
- `TELEGRAM_BOT_TOKEN`;
- `TELEGRAM_WEBHOOK_SECRET`;
- Telegram user IDs владельца;
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
- [`docs/operations/TELEGRAM_COMPANION_RUNBOOK.md`](docs/operations/TELEGRAM_COMPANION_RUNBOOK.md) — Telegram deployment.
- [`knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt`](knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt) — асинхронный отчёт.
- [`knowledge/12_TELEGRAM_COMPANION.txt`](knowledge/12_TELEGRAM_COMPANION.txt) — Telegram contract.
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

## Локальный запуск Telegram Companion

```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_WEBHOOK_SECRET="..."
export TELEGRAM_ALLOWED_USER_IDS="123456789"
export OMNI_GATEWAY_URL="https://omni-cio-gateway-au6d.onrender.com"
export OMNI_GATEWAY_API_KEY="..."
export TELEGRAM_PUBLIC_BASE_URL="https://your-public-tunnel.example"
export TELEGRAM_GATEWAY_RETRY_ATTEMPTS="2"
export TELEGRAM_GATEWAY_RETRY_DELAY_SECONDS="5"
uvicorn telegram_bot.app:app --reload
```

В Windows PowerShell используйте `$env:NAME="value"` вместо `export`.

## Проверки

```bash
python scripts/check_repository_layout.py
python -m compileall -q app.py app_v371.py app_v360.py main.py \
  portfolio_market.py portfolio_analytics.py cash_liquidity.py \
  purchase_capacity.py purchase_capacity_integrity.py \
  operations_analytics.py broker_report_reconciliation telegram_bot tests scripts
python -m pytest -q
```

Regression Shield контролирует оба сервиса, стабильный `app:app`, Telegram entrypoint, webhook security, отсутствие торговых функций и `trading_methods=false`.

## Деплой

- Gateway: [`render.yaml`](render.yaml), entrypoint `app:app`.
- Telegram: [`render.telegram.yaml`](render.telegram.yaml), entrypoint `telegram_bot.app:app`.

Telegram Blueprint использует `autoDeployTrigger: checksPass`: деплой начинается только после успешного CI.

## Важная граница проекта

Исходный frontend существующего сайта Omni-CIO пока не закреплён за этим репозиторием. Не создавайте дубликат сайта.
