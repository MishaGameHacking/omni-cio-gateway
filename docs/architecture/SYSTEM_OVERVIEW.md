# Архитектура системы Omni-CIO

## 1. Границы репозитория

`Misha2304/omni-cio-gateway` содержит backend-шлюз, тесты, OpenAPI-контракт, правила Custom GPT и обезличенную проектную память.

Репозиторий не является хранилищем пользовательских финансовых данных и не содержит торговых методов.

## 2. Основной поток данных

```text
Пользователь
  ↓
Custom GPT Omni-CIO
  ↓ Bearer GATEWAY_API_KEY
FastAPI gateway на Render (`app:app`)
  ↓ read-only TINVEST_TOKEN
T-Invest API
```

Дополнительные будущие источники веб-кабинета:

```text
Официальный HTML-отчёт СберИнвестиций → безопасный parser → нормализованная модель
MOEX ISS → отдельная текущая рыночная оценка
```

## 3. Runtime-модули

- `app.py` — актуальный стабильный entrypoint и release wrapper v3.9.1.
- `app_v371.py` — архивный совместимый слой, на котором закреплены существующие маршруты.
- `app_v360.py` — более ранний базовый слой gateway.
- `main.py` — исторический базовый FastAPI-модуль и общие функции.
- `portfolio_market.py` — рыночная оценка портфеля.
- `portfolio_analytics.py` — аналитика структуры и концентрации.
- `cash_liquidity.py` — диагностика денег и лимитов вывода.
- `purchase_capacity.py` — read-only preview покупательной способности.
- `purchase_capacity_integrity.py` — арифметическая и комиссионная целостность preview.
- `sdk_order_compat.py` — адаптер read-only методов SDK для расчётов.
- `operations_analytics.py` — операции и сверка денежных потоков.
- `broker_report_reconciliation/` — официальный брокерский отчёт, пагинация и сверка.

Исторические wrapper-файлы пока остаются в корне, потому что изменение импортов может повлиять на production. Их перенос выполняется только отдельным рефакторингом с полным Regression Shield.

## 4. Контракты безопасности

- Пользовательские endpoints только `GET`.
- Bearer-проверка через `GATEWAY_API_KEY`.
- Токен T-Invest имеет read-only назначение.
- `trading_methods=false`.
- Счёт маскируется.
- Ошибки очищаются от секретов.
- Валюты не агрегируются без подтверждённого FX.

## 5. Качество и частичные ответы

Каждая сложная операция возвращает источник, статус компонентов, `quality`, `complete`, `component_errors` и `warnings`. Ошибка одного компонента может дать безопасный `partial`, но не должна превращаться в ложный `ok`.

## 6. Деплой

Render использует `render.yaml` и команду:

```text
uvicorn app:app --host 0.0.0.0 --port $PORT
```

После каждого merge проверяются `/health`, версия, commit SHA, Regression Shield и OpenAPI.
