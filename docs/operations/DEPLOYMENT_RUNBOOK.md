# Runbook: Render deployment

## Production contract

- Platform: Render Web Service.
- Единственный production service: `omni-cio-gateway`.
- Production URL: `https://omni-cio-gateway.onrender.com`.
- Entrypoint: `app:app`.
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`.
- Health path: `/health`.
- Build command: `pip install --require-hashes -r requirements.txt`.
- `render.yaml` хранится в GitHub как declarative/recovery contract для одного сервиса и не требует активного Render Blueprint.

## Single-service rule

Production topology должна содержать только один рабочий Gateway:

`omni-cio-gateway`

Не создавать второй Render Web Service из `render.yaml`, если существующий `omni-cio-gateway` уже подключён к `main` и работает. Не создавать параллельные `*-au6d`, Telegram/publishing services или другие дубликаты без отдельного решения владельца.

Если Blueprint был отключён, это нормально: существующий Web Service может продолжать Auto-Deploy из GitHub `main`. `render.yaml` остаётся резервным описанием безопасной конфигурации и не должен сам по себе порождать дополнительный production service.

## Required environment variables

- `TINVEST_TOKEN` — задаётся только в Render.
- `GATEWAY_API_KEY` — задаётся только в Render и совпадает с Bearer key в GPT Actions.
- `SSL_TBANK_VERIFY=True`.
- `RENDER_EXTERNAL_URL` — задаётся Render автоматически.

## После merge в main

1. Открыть единственный Render service `omni-cio-gateway`.
2. Убедиться, что source repository — `MishaGameHacking/omni-cio-gateway`, branch — `main`.
3. Убедиться, что source commit совпадает с merge commit.
4. Дождаться статуса Live.
5. Проверить логи запуска: `uvicorn app:app`.
6. Открыть `/health` с cache-busting query, например `?check=<timestamp>`.
7. Проверить:
   - `status=ok`;
   - актуальную `version`;
   - `build.commit_sha`;
   - `build.entrypoint=app:app`;
   - `regression_shield.read_only=true`;
   - `trading_methods=false`.
8. Вызвать только `getConnection`, если нужно подтвердить T-Invest token и счёт.
9. Обновить Action schema в GPT Editor только если PR действительно менял публичный OpenAPI contract.

## Если Render показывает старую версию

1. Сравнить source commit Render и `main`.
2. Проверить Start Command — он должен ссылаться на `app:app`, а не `main:app`.
3. Выполнить Manual Deploy → Deploy latest commit.
4. Очистить только build cache, если commit правильный, а артефакт остаётся старым.
5. Добавить query к `/health`, чтобы исключить браузерный cache.
6. Не менять код версии вручную в Render.

## Если снова появились лишние Render services

1. Сначала определить, какой сервис использует production URL `https://omni-cio-gateway.onrender.com`.
2. Не удалять этот сервис.
3. Проверить, не создан ли лишний сервис через Blueprint или старую ручную конфигурацию.
4. Отключить Blueprint/источник автоматического воссоздания лишнего сервиса до удаления самого сервиса.
5. Удалять только подтверждённый дубликат.
6. После удаления проверить, что `omni-cio-gateway` остаётся Live и `/health` отвечает `200`/`status=ok`.

## Rollback

Rollback допустим только на последний известный исправный deploy. После rollback:

- зафиксировать причину в Issue;
- не менять `GATEWAY_API_KEY` без признаков компрометации;
- проверить read-only инварианты;
- подготовить исправление через новую ветку и PR.
