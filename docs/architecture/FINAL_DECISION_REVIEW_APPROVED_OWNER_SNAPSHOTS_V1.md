# Final decision review approved owner snapshots v1

## Назначение

PR-82 сохраняет точные типизированные входы уже успешно выполненного allowlisted calculator invocation, чтобы последующий authenticated server lifecycle мог получить те же Decision/intent/capacity/pro-forma/preview owners без реконструкции данных из HTTP query.

## Граница доверия

Snapshot создаётся только после успешной публикации trusted scenario через `FinalDecisionReviewApprovedInvocationV1`.

Хранятся только process-local typed objects:

- `DecisionSetV1`;
- `CapacityIntentDecisionGateRequestV1`;
- `CapacityAssessmentV1`;
- explicit `ProFormaRiskScenarioV1`;
- purchase или sell previews;
- `scenario_id`, trusted `correlation_id`, operation и masked account.

Не принимаются и не сохраняются:

- Action request body или произвольный raw payload;
- Bearer/API credentials;
- полный brokerage account ID;
- provider names из пользовательского запроса;
- торговые команды.

## Exact rebinding

Исходный calculator invocation ID не переиспользуется. При выборе snapshot для `FinalDecisionReviewApprovedServerContextV1` создаются новые owner ports, которые принимают только точный `context.invocation_request()`.

Ключ выбора:

```text
scenario_id + trusted correlation_id + operation + masked account
```

Mismatch, отсутствие, истечение TTL или устаревший pro-forma scenario дают `None`/fail-closed. Синтетический `DecisionSetV1` не создаётся.

## Lifecycle

1. Allowlisted calculator invocation успешно публикует trusted scenario.
2. Snapshot store проверяет account, direction, timestamps, capacity requests и preview coverage.
3. Typed snapshot сохраняется в bounded process-local store.
4. Authenticated route в следующем пакете сможет выбрать snapshot по server-derived context.
5. Ports будут привязаны к новому invocation ID и переданы существующему PR-80 installation boundary.

## Runtime invariants

- startup snapshot count: `0`;
- broker calls at registration: `0`;
- HTTP/OpenAPI changes: `0`;
- order creation/replace/cancel: `0`;
- `trading_methods=false`;
- Render entrypoint remains `app:app`;
- public GPT Actions remain exactly 14 authenticated GET operations.

## Не входит в PR-82

- вызов PR-80 из authenticated GET lifecycle;
- изменение compact final-review response;
- Render/Gateway/GPT Editor acceptance;
- торговое исполнение.

Следующий пакет должен выбрать snapshot после authenticated context capture, вызвать existing PR-80 one-shot installation и сохранить безопасное внутреннее evidence, не меняя внешний API.
