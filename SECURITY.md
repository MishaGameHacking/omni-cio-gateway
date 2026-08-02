# Omni-CIO security policy

Omni-CIO работает с финансовыми данными. Production T-Invest contour и реальный счёт остаются строго read-only. Единственное разрешённое write-исключение — отдельно включаемая T-Invest Sandbox-песочница с виртуальными деньгами.

## Секреты и приватные данные

Никогда не публиковать в GitHub Issues, Pull Requests, source files или документации:

- значение `TINVEST_TOKEN`;
- значение `TINVEST_SANDBOX_TOKEN`;
- будущие full-access/transfer-access broker token values;
- значение `GATEWAY_API_KEY`;
- Authorization/Bearer headers;
- полный broker account ID;
- реальные приватные broker reports/positions/operations;
- Render/GPT credentials;
- private keys/certificates.

Использовать только безопасные placeholders и маскированные идентификаторы.

## Критические production runtime-инварианты

- Реальный `TINVEST_TOKEN` остаётся read-only.
- Реальные broker writes отсутствуют.
- `trading_methods=false` продолжает обозначать запрет real-money execution.
- Нет withdrawal/transfer surface.
- `app:app` — стабильный production entrypoint.
- Secrets поступают через environment variables.
- Account identifiers повторно маскируются перед user-facing output.
- Ошибки очищаются от sensitive payload before exposure.
- Purchase/sale-capacity logic не создаёт реальных заявок.

## T-Invest Sandbox boundary

Sandbox execution может быть зарегистрирован только при `SANDBOX_TRADING_ENABLED=true`.

Защитные требования:

- outbound host жёстко фиксирован на `sandbox-invest-public-api.tbank.ru`;
- используется отдельный `TINVEST_SANDBOX_TOKEN`;
- `TINVEST_TOKEN` не передаётся sandbox-клиенту;
- sandbox responses явно маркируются `sandbox=true` и `real_money=false`;
- поддерживаются только allowlisted `SandboxService` методы;
- transfer/withdrawal и production `OrdersService/PostOrder` не входят в sandbox package;
- `confirmMarginTrade=false`;
- BUY sizing сверяется только с own-funds limits;
- SELL sizing сверяется только с own-position limits;
- proposal не является submit: сначала формируется неизменяемое предложение, затем требуется отдельное подтверждение;
- подтверждение HMAC-bound к параметрам, имеет короткий TTL и не может менять заявку при execution;
- broker limits повторно проверяются непосредственно перед submit;
- request `orderId` — UUID/idempotency key;
- повтор execution после успешного submit не создаёт вторую заявку;
- timeout/5xx после submit считается неоднозначным состоянием и никогда не приводит к автоматическому повторному submit;
- закрытие/пополнение/отмена Sandbox требуют явных подтверждений;
- sandbox account ID также маскируется в user-facing payload.

In-memory proposal state намеренно fail-closed: restart Render инвалидирует неподтверждённый proposal; пользователь должен сформировать новый proposal. Это безопаснее, чем восстанавливать незавершённое подтверждение без отдельного durable execution journal.

## Custom GPT boundary

- До Sandbox owner acceptance production Instructions остаются `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`.
- OpenAPI импортируется только из production Gateway.
- Authentication: API Key → Bearer с `GATEWAY_API_KEY`.
- Broker tokens не передаются в GPT Editor.
- При `SANDBOX_TRADING_ENABLED=false` expected surface остаётся exactly 14 GET Actions.
- Mutating Sandbox Actions публикуются только после явного enable и помечаются consequential.
- Серверное подтверждение обязательно даже если UI дополнительно запрашивает approval.
- Apps не используются одновременно с Actions.
- GitHub не содержит фактически применённый Bearer secret и не синхронизирует GPT Editor автоматически.

## Data integrity

- Не смешивать валюты без verified FX + timestamp.
- Для денег использовать exact decimal logic.
- Partial/truncated/stale/contradictory data fail closed.
- Не double-count commissions/child operations/embedded trades.
- last price не выдавать за гарантированную executable price.
- при отсутствии fresh market data exact sizing real decision блокируется.
- Sandbox execution не интерпретируется как доказательство production fill/price behavior.

## Dependency and CI security

- Runtime/dev dependencies pinned и hash-locked.
- Lock files не редактируются вручную.
- External GitHub Actions pinned full commit SHA.
- Regression Shield проверяет compile, lint, types, contracts, tests, coverage, dependency audit, SAST and secret scan.
- Merge gates не должны использовать broad `continue-on-error` для security/contract checks.

## Перед merge обычного read-only release

Подтвердить:

- stable `app:app`;
- при выключенном Sandbox exactly 14 GET Actions;
- real broker-write surface count = 0;
- `trading_methods=false` для реального контура;
- Bearer boundary работает;
- OpenAPI валиден;
- repository layout check проходит;
- dependency locks согласованы;
- Ruff/format/mypy проходят;
- branch-inclusive coverage >=60%;
- dependency audit проходит;
- Bandit medium/high findings отсутствуют либо обработаны по узкой документированной policy;
- secret scan проходит.

## Перед merge Sandbox execution release

Дополнительно подтвердить:

- `SANDBOX_TRADING_ENABLED` по умолчанию выключен;
- static boundary исключает production write host/method;
- неверное/истёкшее подтверждение не отправляет заявку;
- own-funds/own-position limit failure блокирует submit;
- preflight повторяется перед submit;
- duplicate execution не создаёт вторую заявку;
- ambiguous submission не retry-ится автоматически;
- sandbox account IDs маскируются;
- no live network tests в CI.

## Production / Sandbox acceptance

Green CI не подтверждает внешний state. После backend/OpenAPI/security-sensitive change отдельно проверить:

1. deployed Render commit;
2. `/health`;
3. auth-negative test;
4. read-only auth-positive routes;
5. при Sandbox enable — `getSandboxTradingStatus`;
6. GPT schema import после появления Sandbox Actions;
7. виртуальный BUY с explicit confirmation;
8. order-state verification;
9. виртуальный SELL с explicit confirmation;
10. duplicate/expiry/tamper negative tests;
11. rollback / kill switch: `SANDBOX_TRADING_ENABLED=false`.

## Сообщение об уязвимости

Не прикладывать реальные secrets или financial payloads. Указать:

- затронутый commit/release;
- endpoint/module;
- шаги воспроизведения на фиктивных данных;
- ожидаемое и фактическое поведение;
- влияние;
- безопасный вариант исправления.
