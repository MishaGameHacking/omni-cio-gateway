# Omni-CIO security policy

Omni-CIO работает с финансовыми данными и должен оставаться строго read-only на Gateway и Custom GPT boundaries.

## Секреты и приватные данные

Никогда не публиковать в GitHub Issues, Pull Requests, source files или документации:

- `TINVEST_TOKEN`;
- значение `GATEWAY_API_KEY`;
- Authorization/Bearer headers;
- полный broker account ID;
- реальные приватные broker reports/positions/operations;
- Render/GPT credentials;
- private keys/certificates.

Использовать только безопасные placeholders и маскированные идентификаторы.

## Критические runtime-инварианты

- `trading_methods=false`.
- User-facing Gateway Actions — GET-only.
- Нет создания, отправки, замены или отмены order/stop-order.
- Нет withdrawal/transfer surface.
- `app:app` — стабильный production entrypoint.
- Secrets поступают через environment variables.
- Account identifiers повторно маскируются перед user-facing output.
- Ошибки очищаются от sensitive payload before exposure.
- Runtime source сканируется на запрещённые broker write methods.
- Purchase-capacity logic остаётся read-only и не создаёт заявки.

## Custom GPT boundary

- Production Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`.
- OpenAPI импортируется только из production Gateway.
- Authentication: API Key → Bearer с `GATEWAY_API_KEY`.
- `TINVEST_TOKEN` не передаётся в GPT Editor.
- Expected surface: exactly 14 GET Actions.
- Apps не используются одновременно с Actions.
- GitHub не содержит фактически применённый Bearer secret и не синхронизирует GPT Editor автоматически.

## Data integrity

- Не смешивать валюты без verified FX + timestamp.
- Для денег использовать exact decimal logic.
- Partial/truncated/stale/contradictory data fail closed.
- Не double-count commissions/child operations/embedded trades.
- last price не выдавать за гарантированную executable price.
- при отсутствии fresh market data exact sizing решения блокируется.

## Dependency and CI security

- Runtime/dev dependencies pinned и hash-locked.
- Lock files не редактируются вручную.
- External GitHub Actions pinned full commit SHA.
- Regression Shield проверяет compile, lint, types, contracts, tests, coverage, dependency audit, SAST and secret scan.
- Merge gates не должны использовать broad `continue-on-error` для security/contract checks.

## Перед merge

Подтвердить:

- stable `app:app`;
- exactly 14 GET Actions;
- forbidden broker-write surface count = 0;
- `trading_methods=false`;
- Bearer boundary работает;
- OpenAPI валиден;
- repository layout check проходит;
- dependency locks согласованы;
- Ruff/format/mypy проходят;
- branch-inclusive coverage >=60%;
- dependency audit проходит;
- Bandit medium/high findings отсутствуют либо обработаны по узкой документированной policy;
- secret scan проходит.

## Production acceptance

Green CI не подтверждает внешний production state. После backend/OpenAPI/security-sensitive change отдельно проверить:

1. deployed Render commit;
2. `/health`;
3. auth-negative test;
4. нужный auth-positive route;
5. GPT schema import, если contract менялся;
6. authenticated Preview;
7. Action list;
8. rollback path.

## Сообщение об уязвимости

Не прикладывать реальные secrets или financial payloads. Указать:

- затронутый commit/release;
- endpoint/module;
- шаги воспроизведения на фиктивных данных;
- ожидаемое и фактическое поведение;
- влияние;
- безопасный вариант исправления.
