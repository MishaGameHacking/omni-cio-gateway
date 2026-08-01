# Omni-CIO GPT — Secrets and Render boundary

Этот файл хранит **только архитектуру и имена переменных**. Значения секретов сюда не записываются.

## Production Render service

Current canonical service for the Custom GPT:

`omni-cio-gateway`

Base URL:

`https://omni-cio-gateway.onrender.com`

Health:

`https://omni-cio-gateway.onrender.com/health`

OpenAPI:

`https://omni-cio-gateway.onrender.com/openapi.json`

Previous Blueprint service `omni-cio-gateway-au6d` is not the active endpoint for this GPT and should not be used for new Action imports.

## Environment variables on Render

На текущем service `omni-cio-gateway` должны существовать:

- `GATEWAY_API_KEY`
- `TINVEST_TOKEN`
- `SSL_TBANK_VERIFY`

Значения не хранить в GitHub.

## Что делает каждый секрет

### `TINVEST_TOKEN`

Используется **только Gateway на Render** для read-only связи с T-Invest API.

Не вставлять:
- в GPT Instructions;
- в GPT Knowledge;
- в GPT Action Authentication;
- в GitHub;
- в issue/PR/comment/log вручную.

### `GATEWAY_API_KEY`

Защищает публичный Omni-CIO Gateway от чужих запросов.

Одно и то же секретное значение должно находиться:
- в Render Environment service `omni-cio-gateway` как `GATEWAY_API_KEY`;
- в Custom GPT Action Authentication как `API Key → Bearer`.

В GitHub хранится только имя переменной, не значение.

### `SSL_TBANK_VERIFY`

Управляет проверкой TLS/SSL соединения с T-Invest согласно runtime-конфигурации проекта.

Production ожидает безопасное значение, предусмотренное `render.yaml` и Gateway runtime.

## Правильная цепочка

Custom GPT
→ Authorization: Bearer <GATEWAY_API_KEY>
→ `https://omni-cio-gateway.onrender.com`
→ TINVEST_TOKEN внутри server environment
→ T-Invest API

Пользовательский GPT не должен напрямую знать T-Invest token.

## Health contract

`/health` может подтверждать наличие конфигурации через boolean/state поля, но не должен возвращать сами секреты.

Ожидаемые инварианты:
- `status=ok`;
- `version=3.10.0`;
- `build.entrypoint=app:app`;
- `trading_methods=false`;
- gateway API key configured;
- T-Invest token configured.

## Rotation

Если нужно заменить `TINVEST_TOKEN`:
1. обновить только Render Environment service `omni-cio-gateway`;
2. дождаться/restart deploy при необходимости;
3. проверить `/health`;
4. протестировать `getConnection` в GPT.

Если нужно заменить `GATEWAY_API_KEY`:
1. обновить Render Environment service `omni-cio-gateway`;
2. обновить Bearer secret в GPT Action Authentication тем же новым значением;
3. проверить `gatewayHealth`;
4. проверить `getConnection`.

GitHub-файлы при простой ротации секретов менять не нужно.

## Запрещено хранить в GitHub

- значения `TINVEST_TOKEN`;
- значения `GATEWAY_API_KEY`;
- Authorization headers;
- полный номер брокерского счёта;
- приватные операции и позиции как конфигурационные данные;
- реальные брокерские отчёты, если они содержат чувствительные данные;
- секретные Render exports.

## Дубликаты Render

Custom GPT v8.4 должен использовать только канонический production URL:

`https://omni-cio-gateway.onrender.com`

Если в Render остаётся `omni-cio-gateway-au6d`, считать его резервным/устаревшим до отдельного решения. Не смешивать его ключи, OpenAPI URL или логи с текущим service `omni-cio-gateway`.
