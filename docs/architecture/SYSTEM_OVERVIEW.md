# Архитектура системы Omni-CIO

## 1. Границы репозитория

`Misha2304/omni-cio-gateway` содержит два runtime-компонента:

- Omni-CIO Gateway для Custom GPT;
- Telegram Companion для командного read-only доступа.

Репозиторий также содержит тесты, OpenAPI-контракт, правила Custom GPT, Telegram runbook и обезличенную проектную память. Он не является хранилищем пользовательских финансовых данных и не содержит торговых методов.

## 2. Основные потоки данных

```text
Пользователь в ChatGPT
  ↓
Custom GPT Omni-CIO
  ↓ Bearer GATEWAY_API_KEY
FastAPI Gateway (`app:app`)
  ↓ read-only TINVEST_TOKEN
T-Invest API
```

```text
Пользователь в Telegram
  ↓
Telegram Bot API
  ↓ secret-protected webhook
Telegram Companion (`telegram_bot.app:app`)
  ↓ GET + Bearer OMNI_GATEWAY_API_KEY
FastAPI Gateway (`app:app`)
  ↓ read-only TINVEST_TOKEN
T-Invest API
```

Telegram Companion не обращается к T-Invest напрямую и не дублирует бизнес-логику Gateway.

Будущие источники веб-кабинета:

```text
HTML-отчёт СберИнвестиций → безопасный parser → нормализованная модель
MOEX ISS → отдельная текущая рыночная оценка
```

## 3. Gateway runtime

- `app.py` — стабильный entrypoint и wrapper v3.9.1.
- `app_v371.py`, `app_v360.py`, `main.py` — совместимые исторические слои.
- `portfolio_market.py` — рыночная оценка.
- `portfolio_analytics.py` — структура и концентрация.
- `cash_liquidity.py` — деньги и лимиты вывода.
- `purchase_capacity.py` — read-only preview.
- `purchase_capacity_integrity.py` — арифметика и комиссии.
- `sdk_order_compat.py` — совместимость SDK.
- `operations_analytics.py` — операции и денежная сверка.
- `broker_report_reconciliation/` — официальный отчёт и пагинация.

## 4. Telegram runtime

- `telegram_bot/config.py` — env parsing и readiness.
- `telegram_bot/clients.py` — Telegram API и GET-only Gateway client.
- `telegram_bot/commands.py` — команды, allowlist, masking, deduplication и rate limit.
- `telegram_bot/app.py` — health, webhook и startup auto-configuration.

Telegram service имеет только:

- `GET /health`;
- `POST /telegram/webhook`.

POST является транспортом входящих сообщений, а не методом изменения брокерского счёта.

## 5. Контракты безопасности

### Gateway

- Actions только GET.
- Bearer `GATEWAY_API_KEY`.
- read-only T-Invest token.
- `trading_methods=false`.

### Telegram

- secret header webhook;
- private chats only;
- allowlist user IDs;
- Gateway GET only;
- повторное маскирование account ID;
- отсутствие токенов в health и сообщениях;
- `trading_methods=false`.

### Общие

- валюты не агрегируются без FX;
- ошибки не раскрывают секреты;
- Telegram не изменяет финансовые значения Gateway;
- сбой Telegram не должен ломать Gateway.

## 6. Качество и частичные ответы

Gateway возвращает `quality`, `complete`, `component_errors` и `warnings`. Telegram передаёт эти поля без ложного улучшения статуса. Длинный ответ может быть сокращён только с явным предупреждением.

## 7. Деплой

Gateway:

```text
render.yaml
uvicorn app:app --host 0.0.0.0 --port $PORT
```

Telegram:

```text
render.telegram.yaml
uvicorn telegram_bot.app:app --host 0.0.0.0 --port $PORT
```

Telegram Blueprint создаёт отдельный service и использует `autoDeployTrigger: checksPass`. После merge проверяются health и commit SHA каждого затронутого сервиса отдельно.
