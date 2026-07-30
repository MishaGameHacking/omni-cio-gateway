# Live read-only final-review workflow producer v1

## Назначение

PR-66 поднимает final-review pipeline на уровень уже существующих typed decision
artifacts. Producer не требует заранее собранный `RiskPreTradeExplanationEnvelopeV1`:
он принимает exactly one buy/sell pre-trade gate, current risk и pro-forma risk,
повторно применяет existing directional/account/freshness/intent gates и вызывает
PR-65 bridge.

Producer является internal Python API. Он не регистрирует FastAPI route и не меняет
OpenAPI.

## Вход

`FinalDecisionReviewWorkflowProducerV1.produce(...)` принимает:

- exactly one `CapacityPreTradeDecisionGateV1` или
  `CapacitySellPreTradeDecisionGateV1`;
- current `RiskPolicyEvaluationV1`;
- pro-forma `RiskPolicyEvaluationV1`;
- safe scenario/correlation/request identifiers;
- timezone-aware production timestamp.

Expected capacity requests извлекаются только из source gate
`base_intent_gate.request.expected_capacity_requests`. Caller не передаёт отдельный
дублирующий intent set, поэтому producer не может незаметно заменить instrument,
side, lot count или reference price.

## Pipeline

1. `compose_capacity_directional_pretrade_review` подтверждает exactly one homogeneous
   direction, source readiness, coverage и exact intent binding.
2. `compose_risk_pretrade_explanation` повторно проверяет masked account context,
   current-risk freshness/readiness, directional-review freshness, capacity and broker
   preview layers.
3. PR-65 bridge строит pro-forma scenario, tamper-evident binding и вызывает PR-63.
4. PR-62 публикует exact compact response в PR-61 registry.
5. Existing authenticated GET возвращает reviewed response.

## No-action semantics

Blocked analytical evidence не повышается до ready state. Stale current risk,
account mismatch, incomplete broker coverage или intent mismatch формируют auditable
`WAIT_FOR_DATA`/no-action artifacts. Если structural contracts остаются валидными,
compact no-action response может быть опубликован для безопасного объяснения причины.

Structural misuse — zero or two directional gates, malformed source object or invalid
producer timestamp — блокируется до publication.

## Source authority

Producer не вызывает брокера и не создаёт preview. Source authority остаётся у typed
purchase/sell gate, который уже содержит retained broker-preview coverage. Producer
только читает эти contracts и сохраняет их в downstream evidence chain.

## Concurrency and lifecycle

- producer-level `RLock` сериализует directional review → explanation → bridge;
- PR-65 and PR-62 сохраняют downstream lock/replacement semantics;
- identical concurrent workflows yield one initial publication and replacements;
- registry TTL, bounded capacity and restart-empty behavior не меняются.

## Safety invariants

`FinalDecisionReviewWorkflowProducerResultV1` фиксирует:

- `internal_only=true`;
- `live_read_only_producer_registered=true` как contract capability;
- повторные authority/freshness/account/intent checks;
- `http_route_created=false`;
- `request_body_created=false`;
- `production_schema_mutated=false`;
- `external_broker_called=false`;
- `source_values_recomputed=false`;
- `trade_authorized=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

## Production accessibility

Producer exported from `omni_cio.release` and is instantiated with the production
`final_decision_review_workflow_bridge`. PR-66 deliberately does not auto-run it and does
not add a user-controlled publication endpoint.

A future runtime coordinator must obtain fresh typed purchase/sell gate and risk evidence
from existing read-only calculations, then invoke this producer inside the process.

## Remaining boundary

PR-66 creates the first complete typed producer from pre-trade/risk artifacts to the
production final-review registry, but it does not itself fetch or schedule those artifacts.
Therefore:

- no startup publication occurs;
- a real coordinator is still required;
- production acceptance evidence remains `not_executed`;
- no autonomous trading is introduced.

## Rollback

Revert PR-66. PR-65 bridge and earlier fail-closed route remain available; an empty
registry continues to return `503`.
