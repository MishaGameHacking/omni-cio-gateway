# Omni-CIO GPT — Secrets and Render boundary

Этот файл хранит **только архитектуру и имена переменных**. Значения секретов сюда не записываются.

## Production Render service

Current service:

`omni-cio-gateway-au6d`

Base URL:

`https://omni-cio-gateway-au6d.onrender.com`

Health:

`https://omni-cio-gateway-au6d.onrender.com/health`

OpenAPI:

`https://omni-cio-gateway-au6d.onrender.com/openapi.json`

## Environment variables on Render

Должны существовать:

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
- в Render Environment как `GATEWAY_API_KEY`;
- в Custom GPT Action Authentication как `API Key → Bearer`.

В GitHub хранится только имя переменной, не значение.

### `SSL_TBANK_VERIFY`

Управляет проверкой TLS/SSL соединения с T-Invest согласно runtime-конфигурации проекта.

Production ожидает безопасное значение, предусмотренное `render.yaml` и Gateway runtime.

## Правильная цепочка

Custom GPT
→ Authorization: Bearer <GATEWAY_API_KEY>
→ Omni-CIO Gateway on Render
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
1. обновить только Render Environment;
2. дождаться/restart deploy при необходимости;
3. проверить `/health`;
4. протестировать `getConnection` в GPT.

Если нужно заменить `GATEWAY_API_KEY`:
1. обновить Render Environment;
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

Custom GPT v8.4 настроен на production URL:

`https://omni-cio-gateway-au6d.onrender.com`

Не переключать GPT на другой Render service только по совпадению имени. Перед изменением обязательно проверить `/health`, версию, commit/deployment и `trading_methods=false`.
