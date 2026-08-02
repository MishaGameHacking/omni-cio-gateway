# Omni-CIO — Secrets and Render boundary

Этот файл хранит только архитектуру и имена переменных. Значения secrets никогда не записываются в GitHub.

## Production Render service

Единственный production service:

`omni-cio-gateway`

Base URL:

`https://omni-cio-gateway.onrender.com`

Health:

`https://omni-cio-gateway.onrender.com/health`

OpenAPI:

`https://omni-cio-gateway.onrender.com/openapi.json`

Не использовать старые/альтернативные Render services. Не создавать второй Gateway, Telegram/publishing service или `*-au6d` duplicate для production Custom GPT.

## Render topology

Текущая целевая схема — один обычный Render Web Service, подключённый к GitHub `main`.

Активный Blueprint не требуется. `render.yaml` хранится в репозитории как declarative/recovery contract для безопасного восстановления одного сервиса. Если существующий `omni-cio-gateway` уже работает, не надо создавать по `render.yaml` ещё один Web Service.

## Render Environment

Production service использует:

- `GATEWAY_API_KEY`
- `TINVEST_TOKEN`
- `SSL_TBANK_VERIFY`

`render.yaml` задаёт безопасный single-service deployment contract и не содержит secret values.

## `TINVEST_TOKEN`

Используется только Gateway на Render для read-only связи с T-Invest API.

Не вставлять его:

- в GPT Instructions;
- в GPT Knowledge;
- в GPT Action Authentication;
- в GitHub;
- в Issue/PR/comment;
- в пользовательский ответ.

## `GATEWAY_API_KEY`

Защищает Omni-CIO Gateway.

Одно и то же secret value должно быть:

- в Render Environment как `GATEWAY_API_KEY`;
- в Custom GPT Action Authentication как `API Key → Bearer`.

GitHub хранит только имя переменной.

## `SSL_TBANK_VERIFY`

Production ожидает TLS verification согласно `render.yaml`/runtime. Не отключать проверку только ради устранения сетевой ошибки без отдельного security analysis.

## Правильная цепочка

```text
Custom GPT
  ↓ Authorization: Bearer <GATEWAY_API_KEY>
Omni-CIO Gateway on Render
  ↓ TINVEST_TOKEN stored server-side
T-Invest API
```

Custom GPT не должен напрямую получать T-Invest token.

## Health contract

`/health` может показывать boolean/configured state, но не secret values.

Ожидается:

- `status=ok`;
- `version=3.10.0`;
- `entrypoint=app:app` или эквивалентный build marker;
- `trading_methods=false`;
- T-Invest token configured;
- Gateway API key configured.

## Rotation

### T-Invest token

1. Обновить только `TINVEST_TOKEN` в Render Environment.
2. Перезапустить/deploy service, если Render требует.
3. Проверить `/health`.
4. Проверить `getConnection` через GPT.

GPT Action Bearer при этом не меняется.

### Gateway key

1. Обновить `GATEWAY_API_KEY` в Render.
2. В GPT Editor заменить Bearer secret тем же новым значением.
3. Проверить `gatewayHealth`/`getConnection`.
4. Не коммитить значение в GitHub.

## Что не хранить в GitHub

- значения `TINVEST_TOKEN`;
- значения `GATEWAY_API_KEY`;
- Authorization headers;
- full account ID;
- private broker reports/operations/positions as configuration data;
- Render secret exports.

## Single-service rule

Canonical production Gateway для Custom GPT один:

`https://omni-cio-gateway.onrender.com`

Перед любым endpoint change требуется отдельная проверка health, version, deployment commit, auth и `trading_methods=false`.

Если в Render снова появился второй сервис, сначала устранить причину его автоматического воссоздания (например, старый Blueprint), затем удалить только подтверждённый дубликат. Рабочий `omni-cio-gateway` не удалять.
