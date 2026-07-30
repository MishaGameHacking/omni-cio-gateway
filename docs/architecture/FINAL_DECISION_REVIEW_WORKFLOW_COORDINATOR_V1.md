# Read-only final-review workflow coordinator v1

## Назначение

PR-67 вводит typed coordinator между source acquisition и PR-66 producer. Coordinator не
загружает данные сам, не вызывает брокера и не планирует работу. Он принимает уже
полученные artifacts вместе с безопасными acquisition outcomes и вызывает producer только
при полном, свежем и согласованном bundle.

## Canonical source slots

Dossier всегда содержит ровно четыре slot:

- `purchase_gate`;
- `sell_gate`;
- `current_risk`;
- `pro_forma_risk`.

Для рабочего bundle exactly one directional gate имеет `available`, невыбранный direction —
`missing`, current risk — `available`, pro-forma risk — `available`.

## Source evidence

Каждый `FinalDecisionReviewWorkflowSourceEvidenceV1` хранит только:

- slot;
- status `available`, `missing` или `failed`;
- UTC observation time для available source;
- safe provider/operation;
- safe error code для failed source;
- fixed false flags для payload, credentials, full account и broker writes.

Financial payload, account values, positions, prices и credentials в evidence не входят.

## Coordinator gates

`FinalDecisionReviewWorkflowCoordinatorV1.coordinate(...)` последовательно проверяет:

1. четыре уникальных canonical slots;
2. exact evidence↔artifact correspondence;
3. exactly one directional artifact;
4. three available + one missing + zero failed;
5. evidence time equals artifact source time;
6. source age and future tolerance;
7. current/pro-forma/preview masked account parity;
8. expected request side equals selected buy/sell direction;
9. только затем вызывает PR-66 producer.

Missing, failed, stale, future-dated, account-mismatched или direction-mismatched bundle не
вызывает producer.

## Result

`FinalDecisionReviewWorkflowCoordinatorResultV1` включает canonical evidence rows,
reconciled counters, completed stage, blocker и optional producer result. Published status
возможен только при published PR-66 result.

## Safety boundary

- `coordinator_performed_network_calls=false`;
- `source_payloads_logged=false`;
- `credentials_logged=false`;
- `full_account_logged=false`;
- `external_broker_called=false`;
- `broker_write_called=false`;
- `trade_authorized=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

## Remaining boundary

PR-67 validates the handoff but does not implement source acquisition. A future adapter must
call existing read-only calculators, construct exact source evidence and pass artifacts to
the coordinator. It must never mark missing data as available.

Production acceptance evidence remains `not_executed` until actual Render/Gateway/GPT and
rollback checks are performed.

## Rollback

Revert PR-67. PR-66 producer and earlier fail-closed route remain unchanged.
