# Omni-CIO Gateway

Приватный read-only шлюз между Custom GPT и T-Invest API. Репозиторий является техническим центром управления backend-частью проекта Omni-CIO Bot.

## Текущее состояние

- Runtime: **v3.9.1 Broker Report Async Integrity**.
- Стабильный Render entrypoint: `app:app`.
- Публичные методы шлюза — только чтение.
- Создание, замена, отмена и отправка заявок запрещены.
- Официальный брокерский отчёт T-Invest формируется асинхронно.
- Ошибка T-Invest `30058` трактуется как штатное состояние `pending`.
- Максимальный период одного официального отчёта: `31` день.

## Как начать работу в новом чате или проекте

1. Подключить GitHub и открыть репозиторий `Misha2304/omni-cio-gateway`.
2. Сначала прочитать `AGENTS.md`.
3. Затем прочитать `knowledge/00_PROJECT_MASTER_CONTEXT.md`.
4. Для брокерского отчёта прочитать `knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt`.
5. Перед изменениями проверить текущую ветку `main`, открытые PR и GitHub Actions.
6. Все изменения делать через отдельную ветку и Pull Request.

## Основные документы

- `AGENTS.md` — обязательные правила для AI-агентов и разработчиков.
- `knowledge/00_PROJECT_MASTER_CONTEXT.md` — единый контекст всего проекта, цели, ограничения и дорожная карта.
- `knowledge/09_MARKET_DATA_AND_BUYING_POWER.txt` — рыночные данные и покупательная способность.
- `knowledge/10_OPERATIONS_ANALYTICS_AND_RECONCILIATION.txt` — операции и сверка денежных потоков.
- `knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt` — официальный брокерский отчёт и асинхронный цикл.
- `.github/copilot-instructions.md` — правила для GitHub Copilot.

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export TINVEST_TOKEN="..."
export GATEWAY_API_KEY="..."
export SSL_TBANK_VERIFY="True"
uvicorn app:app --reload
```

В Windows PowerShell используйте `$env:NAME="value"` вместо `export`.

## Переменные окружения

Секретные значения нельзя сохранять в Git, Issues, Pull Requests, логах или документации.

- `TINVEST_TOKEN` — токен T-Invest.
- `GATEWAY_API_KEY` — Bearer-ключ шлюза для GPT Actions.
- `SSL_TBANK_VERIFY=True` — проверка TLS T-Bank SDK.
- `RENDER_EXTERNAL_URL` — публичный URL Render, задаётся платформой автоматически.

Пример без секретов находится в `.env.example`.

## Проверки перед слиянием

```bash
python -m compileall .
python -m pytest -q
```

Дополнительно проверить:

- `/health` возвращает актуальную версию;
- OpenAPI содержит уникальные `operationId`;
- все response object schemas имеют явные `properties`;
- в OpenAPI отсутствуют торговые методы;
- `trading_methods=false`;
- Render entrypoint остаётся `app:app`;
- суммы разных валют не складываются без подтверждённого FX-источника.

## Деплой

Render использует `render.yaml`:

```text
build: pip install -r requirements.txt
start: uvicorn app:app --host 0.0.0.0 --port $PORT
health: /health
```

После merge в `main` проверить новый деплой и только затем обновлять Action-схему Custom GPT.

## Безопасность

Проект предназначен для анализа, диагностики и сверки данных. Он не должен совершать сделки. Номер счёта всегда маскируется. Токены и ключи никогда не выводятся пользователю и не записываются в репозиторий.
