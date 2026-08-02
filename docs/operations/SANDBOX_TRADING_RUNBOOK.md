# T-Invest Sandbox trading — owner runbook

Этот runbook относится только к виртуальным сделкам T-Invest Sandbox. Он не включает real-money trading.

## 1. Архитектура

```text
Custom GPT
   │  HTTPS + GATEWAY_API_KEY
   ▼
Omni-CIO Gateway / Render
   │
   ├── TINVEST_TOKEN ───────────────► production T-Invest read-only
   │
   └── TINVEST_SANDBOX_TOKEN ──────► sandbox-invest-public-api.tbank.ru/rest
                                      SandboxService only
```

`TINVEST_TOKEN` не заменяется и не повышается до full-access для Sandbox-тестов.

## 2. Kill switch

Sandbox Actions регистрируются только когда в Render выставлено:

```text
SANDBOX_TRADING_ENABLED=true
```

При отсутствии переменной или значении `false` production OpenAPI остаётся на старом read-only surface.

Мгновенный rollback Sandbox-функции:

```text
SANDBOX_TRADING_ENABLED=false
```

После изменения environment выполнить Render redeploy/restart и повторно импортировать OpenAPI в GPT Editor, если менялся опубликованный Action surface.

## 3. Секреты Render

В `omni-cio-gateway → Environment` должны быть:

```text
TINVEST_TOKEN=<существующий read-only token, НЕ МЕНЯТЬ>
GATEWAY_API_KEY=<существующий Gateway bearer secret, НЕ МЕНЯТЬ>
TINVEST_SANDBOX_TOKEN=<отдельный Sandbox token>
SANDBOX_TRADING_ENABLED=true
SANDBOX_CONFIRMATION_TTL_SECONDS=120
```

Никогда не помещать значения токенов в GitHub, GPT Instructions, Knowledge, чат или screenshot.

## 4. Sandbox account bootstrap

1. `getSandboxTradingStatus`.
2. Если открытого sandbox-счёта нет — `openSandboxAccount` только после явного подтверждения:
   `ПОДТВЕРЖДАЮ СОЗДАНИЕ ПЕСОЧНИЦЫ`.
3. `fundSandboxAccount` только после явного подтверждения:
   `ПОДТВЕРЖДАЮ ПОПОЛНЕНИЕ ПЕСОЧНИЦЫ`.
4. Проверить `getSandboxPortfolio`.

Autonomous routing требует ровно один открытый Sandbox account. Несколько открытых счетов → fail closed.

## 5. BUY acceptance

Использовать небольшой ликвидный инструмент и 1 лот.

1. Подтвердить instrument id через текущие read-only instrument/market Actions.
2. Вызвать `prepareSandboxTrade` с `direction=BUY` и коротким rationale.
3. Проверить:
   - `sandbox=true`;
   - `real_money=false`;
   - account masked;
   - own-funds max-lots preflight прошёл;
   - `requires_user_confirmation=true`;
   - получена уникальная фраза `ПОДТВЕРЖДАЮ SANDBOX <code>`;
   - до подтверждения в Sandbox нет новой заявки.
4. Пользователь вручную отправляет точную confirmation phrase.
5. Только после этого `executeSandboxTrade`.
6. `getSandboxOrderState` по returned request/order id.
7. `getSandboxPortfolio` и убедиться, что виртуальная позиция изменилась.

## 6. SELL acceptance

1. Выбрать позицию, реально имеющуюся в Sandbox portfolio.
2. `prepareSandboxTrade` с `direction=SELL`, 1 lot.
3. Убедиться, что own-position `sellMaxLots` допускает заявку.
4. Пользователь вручную подтверждает exact phrase.
5. `executeSandboxTrade`.
6. `getSandboxOrderState`.
7. `getSandboxPortfolio` — виртуальная позиция должна уменьшиться/закрыться в соответствии с исполнением.

## 7. Cancel acceptance

Для теста отмены создать в Sandbox заведомо неисполняемую/далёкую limit order только после обычного proposal + confirmation workflow.

Затем `cancelSandboxOrder` допускается только при точном подтверждении:

```text
ПОДТВЕРЖДАЮ ОТМЕНУ SANDBOX
```

После отмены проверить `getSandboxOrderState`.

## 8. Негативные тесты

Обязательные сценарии:

- неверная confirmation phrase → HTTP 403 / submit отсутствует;
- confirmation старше TTL → HTTP 409 / submit отсутствует;
- попытка quantity выше own-funds/own-position max lots → blocked;
- повторный `executeSandboxTrade` того же успешного proposal → второй broker submit отсутствует;
- Render restart после `prepare` → proposal исчезает и должен быть создан заново;
- timeout/5xx после submit → состояние `unknown_do_not_resubmit`, автоматического повторного submit нет;
- два открытых Sandbox accounts → autonomous submit блокируется;
- `SANDBOX_TRADING_ENABLED=false` → sandbox routes исчезают из OpenAPI;
- production `TINVEST_TOKEN` остаётся read-only независимо от Sandbox теста.

## 9. Что считать успешным Sandbox acceptance

Acceptance пройден только если одновременно:

- exact-head Regression Shield green;
- production read-only smoke tests не регрессировали;
- virtual BUY прошёл;
- BUY order state подтверждён;
- virtual SELL прошёл;
- SELL order state подтверждён;
- duplicate/expiry/tamper tests fail closed;
- account ids masked;
- kill switch подтверждён;
- ни один тест не изменил реальный брокерский счёт.

После этого можно открывать отдельный design/PR для real-money execution. Sandbox token не переиспользуется как real trading token.

## 10. Real-money переход — отдельный release

Не делать в Sandbox PR:

- замену `TINVEST_TOKEN` на full-access;
- production `OrdersService/PostOrder`;
- production cancel/replace;
- transfer-access token;
- вывод/перевод денег;
- margin automation;
- stop-order automation.

Real-money release требует отдельного kill switch, отдельного account-specific full-access token, повторного user confirmation protocol, production order reconciliation и controlled small-size acceptance.
