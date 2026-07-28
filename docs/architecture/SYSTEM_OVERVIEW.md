# Архитектура системы Omni-CIO

## 1. Границы репозитория

`Misha2304/omni-cio-gateway` содержит один production runtime-компонент:

- Omni-CIO Gateway для Custom GPT;

Репозиторий также содержит тесты, OpenAPI-контракт, правила Custom GPT
и обезличенную проектную память. Он не является хранилищем
пользовательских финансовых данных и не содержит торговых методов.

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

## 4. Пользовательский интерфейс

Custom GPT внутри ChatGPT является единственным поддерживаемым
пользовательским интерфейсом. Канонические instructions и каталог
Actions находятся в `gpt/`.

Telegram runtime выведен из эксплуатации. `telegram_bot/`,
`render.telegram.yaml` и `/telegram/webhook` отсутствуют и блокируются
repository checks.

## 5. Контракты безопасности

### Gateway

- Actions только GET.
- Bearer `GATEWAY_API_KEY`.
- read-only T-Invest token.
- `trading_methods=false`.

### Общие

- валюты не агрегируются без FX;
- ошибки не раскрывают секреты;
- выведенные transport integrations не импортируются Gateway.

## 6. Качество и частичные ответы

Gateway возвращает `quality`, `complete`, `component_errors` и
`warnings`. Custom GPT обязан показывать ограничения без ложного
улучшения статуса.

## 7. Деплой

Gateway:

```text
render.yaml
pip install --require-hashes -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port $PORT
```

Dependency lock содержит точные версии и SHA-256 hashes. Regression
Shield отдельно проверяет качество, покрытие, зависимости, код,
секреты и full-SHA Action pins.

После merge проверяются health и commit SHA Gateway. Старый Telegram
service, webhook и token удалены владельцем 2026-07-28.
