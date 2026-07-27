# Runbook: Render deployment

## Production contract

- Platform: Render Web Service.
- Entrypoint: `app:app`.
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`.
- Health path: `/health`.
- Configuration source: `render.yaml`.

## Required environment variables

- `TINVEST_TOKEN` — задаётся только в Render.
- `GATEWAY_API_KEY` — задаётся только в Render и совпадает с Bearer key в GPT Actions.
- `SSL_TBANK_VERIFY=True`.
- `RENDER_EXTERNAL_URL` — задаётся Render автоматически.

## После merge в main

1. Открыть Render Deploys.
2. Убедиться, что source commit совпадает с merge commit.
3. Дождаться статуса Live.
4. Проверить логи запуска: `uvicorn app:app`.
5. Открыть `/health` с cache-busting query, например `?check=<timestamp>`.
6. Проверить:
   - `status=ok`;
   - актуальную `version`;
   - `build.commit_sha`;
   - `build.entrypoint=app:app`;
   - `regression_shield.read_only=true`;
   - `trading_methods=false`.
7. Вызвать только `getConnection`, если нужно подтвердить T-Invest token и счёт.
8. После успешного production smoke test обновить Action schema в GPT Editor.

## Если Render показывает старую версию

1. Сравнить source commit Render и `main`.
2. Проверить Start Command — он должен ссылаться на `app:app`, а не `main:app`.
3. Выполнить Manual Deploy → Deploy latest commit.
4. Очистить только build cache, если commit правильный, а артефакт остаётся старым.
5. Добавить query к `/health`, чтобы исключить браузерный cache.
6. Не менять код версии вручную в Render.

## Rollback

Rollback допустим только на последний известный исправный deploy. После rollback:

- зафиксировать причину в Issue;
- не менять `GATEWAY_API_KEY` без признаков компрометации;
- проверить read-only инварианты;
- подготовить исправление через новую ветку и PR.
