# Read-only final-review source acquisition adapter v1

## Назначение

PR-68 вводит typed acquisition boundary перед PR-67 coordinator. Adapter получает четыре
инъецированных read-only loader port, преобразует реальные outcomes в canonical evidence и
передаёт coordinator точные artifacts. Он не создаёт HTTP route и не знает credentials.

## Loader ports

- purchase pre-trade gate;
- sell pre-trade gate;
- current risk;
- pro-forma risk.

Для одного вызова выбирается `buy` или `sell`. Adapter вызывает только выбранный gate и оба
risk port. Невыбранный gate не вызывается и записывается как `missing` с
`attempted=false`.

Каждый port содержит только slot, safe provider/operation, expected artifact type, callable
и timestamp resolver.

## Outcome mapping

- valid typed artifact + aware source time → `available`;
- loader returns `None` → `missing`, `attempted=true`;
- unselected direction → `missing`, `attempted=false`;
- `TimeoutError` → `failed/SOURCE_TIMEOUT`;
- other loader exception → `failed/SOURCE_LOAD_FAILED`;
- wrong artifact type → `failed/SOURCE_TYPE_INVALID`;
- absent/naïve source timestamp → `failed/SOURCE_TIMESTAMP_INVALID`.

Raw exception text, traceback, payload and credentials are discarded.

## Coordinator handoff

Adapter always constructs four ordered PR-67 evidence slots. Artifact presence must match
evidence availability exactly. Coordinator receives the exact loaded objects; adapter does
not clone, synthesize or substitute source contracts.

Incomplete or failed acquisition is still passed as explicit evidence so PR-67 returns an
auditable blocked result. Adapter never promotes failed or missing data to available.

## Concurrency

One adapter-level `RLock` serializes selected port calls through coordinator handoff.
Downstream coordinator, producer, bridge and publisher retain their own locks and exact
replacement semantics.

## Safety invariants

- `user_controlled_publication_surface=false`;
- `request_body_created=false`;
- `payload_logged=false`;
- `credentials_logged=false`;
- `full_account_logged=false`;
- `exception_text_logged=false`;
- `broker_write_called=false`;
- `trade_authorized=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

## Remaining boundary

PR-68 provides the adapter and loader ports but does not wire concrete production loaders.
A later package must connect existing read-only calculators to the ports, preserve their
source timestamps and never expose secrets or broker writes.

Production Render/GPT/rollback acceptance remains `not_executed`.

## Rollback

Revert PR-68. PR-67 coordinator and previous final-review chain remain unchanged.
