# Final decision-review workflow bridge v1

## Назначение

PR-65 добавляет process-local production boundary между уже проверенными risk/pre-trade
artifacts и PR-63 orchestration. Bridge зарегистрирован в `app.py` как
`final_decision_review_workflow_bridge`, но не является HTTP Action и не добавляет новый
route.

## Вход

`FinalDecisionReviewWorkflowBridgeV1.publish(...)` принимает только типизированные
внутренние объекты:

- `RiskPreTradeExplanationEnvelopeV1` — current account/risk и exact reviewed intent;
- ordered `CapacityOrderRequestV1` set — предполагаемое изменение;
- `RiskPolicyEvaluationV1` — уже рассчитанный pro-forma post-change risk;
- safe scenario/correlation/request identifiers;
- timezone-aware bridge timestamp.

Credentials, full account ID, raw request body, order confirmation и execution controls не
являются частью API.

## Pipeline

1. `build_pro_forma_risk_scenario` связывает supplied risk evidence с account, direction,
   option и exact capacity-request set.
2. `bind_pro_forma_risk_to_intent` сравнивает scenario с base explanation.
3. PR-63 строит response/shadow, release eligibility, Action shadow, input binding,
   readiness dossier и route plan.
4. PR-62 публикует exact source в PR-61 bounded TTL registry.
5. Existing authenticated `GET /decision/final-review` возвращает compact response.

Bridge не пересчитывает portfolio risk и не вызывает broker SDK. Timestamp scenario берётся
из `pro_forma_risk_evaluation.metadata.retrieved_at`; bridge timestamp используется для
freshness and publication checks.

## Fail-closed behavior

- invalid/empty/heterogeneous scenario → blocked at `scenario`;
- structurally invalid binding → blocked at `binding`;
- missing HTTPS OpenAPI server, schema drift or trace failure → blocked at
  `orchestration`;
- exact intent substitution формирует safe no-action binding and response instead of
  upgrading the decision;
- downstream PR-63 blocker is preserved as the primary blocker;
- registry is not mutated on blocked publication.

## Production registration

`app.py` creates one object after the final OpenAPI patch:

```python
final_decision_review_workflow_bridge = FinalDecisionReviewWorkflowBridgeV1(
    registry=final_decision_review_registry,
    openapi_provider=lambda: app.openapi(),
    expected_app_version=APP_VERSION,
)
```

OpenAPI is read lazily and deep-copied by the bridge/orchestration chain. Production schema
and its cache are not modified.

## Concurrency and lifecycle

- one bridge-level `RLock` serializes scenario → binding → publication for this process;
- PR-62 still owns exact registry replacement semantics;
- identical concurrent calls yield one first publication and replacements afterward;
- PR-61 TTL and bounded capacity remain unchanged;
- process restart creates an empty registry;
- a caller must invoke the bridge again after restart.

## Safety invariants

`FinalDecisionReviewWorkflowBridgeResultV1` fixes:

- `internal_only=true`;
- `production_bridge_registered=true`;
- `http_route_created=false`;
- `request_body_created=false`;
- `production_schema_mutated=false`;
- `external_broker_called=false`;
- `source_values_recomputed=false`;
- `trade_authorized=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

## Remaining boundary

PR-65 makes a production-importable bridge available, but the repository still has no live
producer that builds `RiskPreTradeExplanationEnvelopeV1` and pro-forma
`RiskPolicyEvaluationV1` from a real user workflow and then invokes this bridge.

Therefore:

- registry is not automatically repopulated at startup;
- exact positive route acceptance may still return `503` until a validated workflow calls
  the bridge;
- Render/GPT acceptance evidence remains `not_executed`;
- no autonomous trade execution is introduced.

## Rollback

Revert PR-65. The existing route remains fail-closed and returns `503` when the registry is
empty. No OpenAPI or external configuration rollback is required.
