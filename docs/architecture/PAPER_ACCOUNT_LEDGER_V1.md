# Paper Account Ledger V1

## Purpose

`build_paper_account_ledger` deterministically replays immutable paper purchase and paper sale results into one currency-local simulated account snapshot.

It closes the state gap between isolated paper scenarios without introducing a database, network service or broker integration.

## Inputs

The reducer accepts:

- one masked account reference;
- one explicit currency;
- non-negative initial paper cash;
- zero or more initial positive-lot paper positions;
- 1–512 ordered `PaperPurchaseResultV1` or `PaperSaleResultV1` objects;
- an aware ledger build timestamp.

Initial positions are bounded to 256 and must have unique stable keys.

## Replay rules

For every result, in caller-provided order:

1. the masked account must match;
2. the currency must match;
3. the result timestamp must not precede the prior result;
4. the ledger build time must not precede the last result;
5. `scenario_id` must be globally unique;
6. result cash-before must equal the current simulated cash;
7. result position-before must equal the current lots for that stable key;
8. an existing instrument cannot change lot size;
9. a known instrument UID cannot change;
10. the result's own purchase or sale contract must already reconcile its atomic state transition.

Any violation rejects the entire ledger. There is no partial replay.

## Event normalization

Each source result becomes one `PaperLedgerEventV1` with:

- contiguous sequence;
- source schema and scenario ID;
- purchase or sale side;
- status;
- stable instrument identity;
- requested and filled lots;
- cash and position before/after;
- purchase cash outflow or sale net proceeds;
- commission;
- estimated tax.

A rejected result is retained as an event and provenance record, but it must contain zero allocated amounts and leave cash and position unchanged.

## State equations

### Purchase

`cash after = cash before − purchase total cost`

`position lots after = position lots before + filled lots`

### Sale

`cash after = cash before + sale net proceeds`

`position lots after = position lots before − filled lots`

A position reaching zero lots is removed from the final snapshot.

## Summary reconciliation

`PaperAccountLedgerV1` independently replays all events from the declared initial state and verifies:

- final cash;
- final sorted positions;
- scenario ID order and uniqueness;
- event sequence and timestamp order;
- total purchase cost;
- total sale net proceeds;
- total commission;
- total estimated tax;
- filled purchase and sale lots;
- rejected-event count.

Tampering with an event, summary total, final state or scenario order invalidates the contract.

## Replay protection

Duplicate scenario IDs fail before replay. This is paper-layer idempotency protection: the same simulated outcome cannot be applied twice to one ledger snapshot.

It is not a real-trading idempotency key and grants no execution authority.

## Provenance and privacy

Every result contributes an allowlisted `SourceReference` containing only:

- provider;
- source operation;
- result timestamp;
- scenario ID.

The ledger stores no raw broker response, token, unmasked account ID, portfolio valuation payload or private document content.

## Persistence boundary

PR-28 produces an immutable snapshot but does not persist it. A caller may serialize the strict contract, but durable storage, encryption, retention, concurrent writes and recovery remain separate later work.

This separation keeps state transition correctness reviewable before introducing operational persistence risks.

## Safety

Every ledger retains:

- `paper_only=true`;
- `broker_order_created=false`;
- `no_cross_currency_aggregation=true`;
- `execution_ready=false`;
- `trading_methods=false`.

The reducer imports no broker SDK, HTTP/gRPC client, SQL library or order-execution adapter.

## Limitations

- One ledger contains one currency only.
- No FX conversion or cross-currency total is produced.
- Tax-lot accounting and realized P&L are not calculated.
- Corporate actions are not yet state transitions.
- Concurrent writers and durable idempotency require a future persistence design.
- The ledger records supplied paper results; it does not model exchange queue priority or improve fill realism.

## Rollback

Revert the PR-28 merge commit. Purchase and sale simulators, public Actions, runtime, Render and broker permissions remain unchanged.
