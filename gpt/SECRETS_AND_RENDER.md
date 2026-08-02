# Omni-CIO — Secrets and Render boundary

Этот файл хранит только архитектуру и имена переменных. Значения secrets никогда не записываются в GitHub.

## Production Render service

Единственный service:

`omni-cio-gateway`

Base URL:

`https://omni-cio-gateway.onrender.com`

Health:

`https://omni-cio-gateway.onrender.com/health`

OpenAPI:

`https://omni-cio-gateway.onrender.com/openapi.json`

Не использовать старые/альтернативные Render services. Не создавать второй Gateway или отдельный trading service ради Sandbox.

## Render topology

Один обычный Render Web Service, подключённый к GitHub `main`.

Активный Blueprint не требуется. `render.yaml` хранится как recovery contract и не должен создавать второй production service, пока текущий `omni-cio-gateway` работает.

## Render Environment — разделение секретов

Базовый production service использует:

- `GATEWAY_API_KEY`;
- `TINVEST_TOKEN`;
- `SSL_TBANK_VERIFY`.

После Sandbox backend acceptance дополнительно:

- `TINVEST_SANDBOX_TOKEN`;
- `SANDBOX_TRADING_ENABLED`;
- `SANDBOX_CONFIRMATION_TTL_SECONDS`.

### Критическое правило

`TINVEST_TOKEN` и `TINVEST_SANDBOX_TOKEN` — разные секреты и выполняют разные роли. Sandbox-тест не требует и не разрешает повышать существующий `TINVEST_TOKEN` до full-access.

Рекомендуемая Sandbox конфигурация:

```text
TINVEST_TOKEN=<существующий read-only production token>
TINVEST_SANDBOX_TOKEN=<отдельный Sandbox token>
GATEWAY_API_KEY=<существующий Gateway secret>
SANDBOX_TRADING_ENABLED=true
SANDBOX_CONFIRMATION_TTL_SECONDS=120
SSL_TBANK_VERIFY=True
```

## `TINVEST_TOKEN`

Production broker credential. В текущей архитектуре остаётся **read-only**.

Не вставлять его:

- в GPT Instructions;
- в GPT Knowledge;
- в GPT Action Authentication;
- в GitHub;
- в Issue/PR/comment;
- в пользовательский ответ.

Sandbox-код не должен читать эту переменную.

## `TINVEST_SANDBOX_TOKEN`

Используется только серверным `omni_cio/sandbox/` контуром для T-Invest Sandbox.

Требования:

- отдельный Sandbox token;
- хранится только в Render Environment;
- не вставляется в GPT Editor;
- не записывается в GitHub;
- не используется против production T-Invest host;
- не переиспользуется как будущий real-money full-access token.

## `SANDBOX_TRADING_ENABLED`

Server-side kill switch.

- отсутствует / `false` → Sandbox routes не регистрируются;
- `true` → Sandbox routes публикуются в `/openapi.json` и требуют `GATEWAY_API_KEY`.

Rollback виртуального execution начинается с возврата:

```text
SANDBOX_TRADING_ENABLED=false
```

и redeploy/restart.

## `SANDBOX_CONFIRMATION_TTL_SECONDS`

TTL конкретного Sandbox trade proposal.

- default: `120` секунд;
- допустимый диапазон runtime: `30..600`;
- истёкший proposal нельзя execute — формируется новый.

## `GATEWAY_API_KEY`

Защищает Omni-CIO Gateway между Custom GPT и Render.

Одно и то же secret value:

- Render Environment: `GATEWAY_API_KEY`;
- Custom GPT Action Authentication: `API Key → Bearer`.

При включении Sandbox **не менять** этот ключ без отдельной причины. Sandbox Actions используют тот же Gateway Bearer, но broker Sandbox token остаётся только внутри Render.

## `SSL_TBANK_VERIFY`

TLS verification не отключать ради устранения сетевой ошибки без отдельного security analysis.

## Правильная цепочка

```text
Custom GPT
  │ Authorization: Bearer <GATEWAY_API_KEY>
  ▼
Omni-CIO Gateway on Render
  ├── <TINVEST_TOKEN> ──────────────► real T-Invest / read-only
  │
  └── <TINVEST_SANDBOX_TOKEN> ─────► T-Invest Sandbox / virtual only
```

Custom GPT не должен напрямую получать ни один T-Invest token.

## Health / acceptance

Baseline `/health` ожидает:

- `status=ok`;
- current Gateway version;
- `entrypoint=app:app`;
- `trading_methods=false` для real-money contour;
- production T-Invest token configured;
- Gateway API key configured.

Sandbox readiness проверять отдельным `getSandboxTradingStatus`, а не переопределять смысл production `/health`.

## Rotation

### Production T-Invest read-only token

1. Обновить только `TINVEST_TOKEN` в Render.
2. Redeploy/restart, если требуется.
3. `/health`.
4. `getConnection` через GPT.

GPT Action Bearer и Sandbox token не меняются.

### Sandbox token

1. Сначала `SANDBOX_TRADING_ENABLED=false`.
2. Обновить только `TINVEST_SANDBOX_TOKEN` в Render.
3. Redeploy/restart.
4. Включить `SANDBOX_TRADING_ENABLED=true`.
5. Redeploy/restart.
6. Проверить `getSandboxTradingStatus`.
7. Выполнить маленький virtual acceptance flow.

### Gateway key

1. Обновить `GATEWAY_API_KEY` в Render.
2. В GPT Editor заменить Bearer secret тем же новым значением.
3. Проверить `gatewayHealth`/`getConnection` и Sandbox status, если Sandbox включён.
4. Не коммитить значение в GitHub.

## Будущий real-money token

Не создавать и не устанавливать его в рамках Sandbox release.

Если после полного Sandbox acceptance будет принято отдельное решение о реальных сделках, использовать **отдельную переменную** для account-specific full-access token. Не заменять read-only `TINVEST_TOKEN` втихую и не использовать transfer-access token без отдельного архитектурного решения.

## Что не хранить в GitHub

- значения `TINVEST_TOKEN`;
- значения `TINVEST_SANDBOX_TOKEN`;
- будущие real full-access/transfer-access token values;
- значения `GATEWAY_API_KEY`;
- Authorization headers;
- full account ID;
- private broker reports/operations/positions as configuration data;
- Render secret exports.

## Single-service rule

Canonical Gateway один:

`https://omni-cio-gateway.onrender.com`

Sandbox — это дополнительный изолированный контур внутри этого сервиса, а не второй Render service.

Полный порядок включения и тестирования: `docs/operations/SANDBOX_TRADING_RUNBOOK.md`.
