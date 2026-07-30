# Final decision review authenticated owner installation v1

## Назначение

PR-83 соединяет PR-81 authenticated server context, PR-82 exact typed owner snapshot и существующий PR-80 one-shot installation boundary.

Маршрут и OpenAPI не меняются. Интеграция выполняется внутри observer, который уже вызывается только после Bearer auth, exact source lookup и успешного handler shadow.

## Последовательность

1. PR-81 создаёт `FinalDecisionReviewApprovedServerContextV1`.
2. Context сохраняется в bounded context store.
3. PR-83 выбирает один PR-82 snapshot по exact key:

```text
scenario_id + trusted correlation_id + operation + masked account
```

4. Snapshot создаёт owner ports, привязанные только к свежему `context.invocation_request()`.
5. Purchase или sell branch выбирается только из typed context operation.
6. PR-80 вызывается один раз.
7. Итог `acquired`, `unavailable` или redacted `failed` сохраняется в bounded evidence store.

## Failure behavior

Missing, stale или mismatched snapshot не вызывает PR-80. Installation/acquisition failure не раскрывает exception text. Существующий compact response не расширяется и не заменяется внутренним evidence.

Evidence содержит только server-derived identifiers, masked account-bound status, blocker/error enums и safety flags. Credentials, raw Action payload, полный account ID и financial owner output наружу не публикуются.

## Runtime lifecycle

- context/evidence TTL: 300 seconds;
- default capacity: 64;
- restart clears both stores;
- duplicate evidence invocation ID is rejected;
- production registration is idempotent for the exact bridge/runtime;
- startup performs zero snapshot selection, owner installation, acquisition, calculator, portfolio, network or broker calls.

## Неизменяемые инварианты

- `app:app`;
- exactly 14 authenticated GET Actions;
- no request body;
- no order create/replace/cancel;
- no transfer or withdrawal;
- `trading_methods=false`.

## Не входит в PR-83

- изменение public final-review response;
- Render/Gateway/GPT Editor production acceptance;
- trading enablement.

Следующий этап после merge должен быть выбран из актуального `knowledge/16_CURRENT_PROGRAM_STATUS.md`; production acceptance PR-64 остаётся отдельным обязательным блоком.
