# Final Decision Review Existing Calculator Providers V1

## Purpose

Adapt existing read-only calculation owners into the PR-75 provider bundle without duplicating or recomputing their financial values.

The package defines typed owner ports and fixed purchase/sell provider IDs. It is a composition boundary, not a calculator.

## Owner ports

The common owner set supplies:

- one typed analytical `DecisionSetV1`;
- one typed exact-intent request;
- one or more typed capacity assessments;
- one explicit typed pro-forma risk evaluation.

The directional owner supplies either purchase previews or sell previews. Purchase and sell outputs are never mixed in one provider.

## Build behavior

On invocation the adapter:

1. checks the exact allowlisted request operation;
2. invokes each configured read-only owner exactly once;
3. rejects exceptions, raw mappings, wrong types and empty required tuples;
4. preserves the pro-forma risk timestamp as the provider bundle timestamp;
5. returns the immutable PR-75 provider bundle with exact scenario/correlation IDs.

No portfolio, capacity, commission, tax, price or risk value is recalculated.

## Registration

`register_existing_calculator_providers` registers only the fixed IDs:

- `provider:existing:purchase-review`;
- `provider:existing:sell-review`.

Registration validates callables but does not invoke any owner, broker or network operation.

## Safety invariants

- internal Python API only;
- explicit owner callables only;
- no dynamic import or user-selected provider name;
- no FastAPI route or operation ID;
- no production OpenAPI change;
- no startup calculation or broker call;
- no broker create, replace or cancel method;
- no credential or full account identifier;
- no trade authorization or execution readiness;
- `trading_methods=false`.

## Remaining boundary

Production still needs to supply concrete owner callables around the already existing Decision Engine, capacity, broker-preview and pro-forma risk owners. The explicit pro-forma risk dependency cannot be inferred or replaced by current-portfolio risk. Render/Gateway/GPT/rollback acceptance remains separate and evidence-driven.

## Rollback

Revert this package. PR-75 and earlier fail-closed registry/invocation layers remain available.
