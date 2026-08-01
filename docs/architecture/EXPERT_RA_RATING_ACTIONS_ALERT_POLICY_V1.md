# Expert RA rating-actions alert policy v1

## Purpose

PR-102 adds one bounded, process-local, global-only operational alert policy over
the privacy-safe PR-101 Expert RA source/cache events. It detects feed-health
conditions only. It does not inspect issuer identity, rating values, rating
actions or financial data, does not send notifications and does not authorize
trading.

## Input boundary

The evaluator accepts `ObservabilityEventV1`. Before any state mutation it:

1. fully reserializes and revalidates the event contract;
2. for the two known Expert RA event names, requires the exact PR-101 component,
   provider, operation, metric names and allowed metric values;
3. requires the opaque `corr:` + 32 `a..p` correlation-id shape;
4. rejects account/request/action/quality/completeness/exception payloads;
5. requires `contains_sensitive_payload=false` and `trading_methods=false`;
6. checks one of the exact source/cache state profiles produced by PR-101.

A forged event that merely copies an Expert RA event name cannot change policy
state.

## Policy contract

`ExpertRaRatingActionsAlertPolicyV1` has fixed scope
`global_expert_ra_rating_actions_feed` and exactly four possible state slots:

- source unavailable;
- cache unavailable;
- stale records explicitly exposed after a failed refresh;
- failed refresh while a still-fresh cached snapshot is used.

Default thresholds:

- source unavailable: 3 consecutive occurrences;
- cache unavailable: 2;
- stale exposed: 2;
- refresh failed using fresh cache: 3;
- cooldown: 900 seconds;
- inactive-state retention: 86400 seconds;
- capacity: exactly 4.

The complete policy is revalidated at evaluator construction. A validator-bypassed
policy cannot raise capacity, enable rating/financial thresholds or change fixed
safety flags.

## Explicit non-financial scope

Policy and evaluation contracts fix these values to false:

- issuer identity present;
- rating values present;
- action identity present;
- rating thresholds present;
- financial thresholds present;
- external notifications enabled/sent;
- broker write called;
- `trading_methods`.

The policy therefore cannot express rules such as rating below `ruBBB`, issuer X,
price, position size, cash level, P&L, portfolio concentration or buy/sell signal.

## State machine

For each of four global kinds the evaluator maintains only:

- consecutive occurrence count;
- active/not-active state;
- last observed timestamp;
- last fired timestamp.

Transitions are:

- below threshold -> `pending`;
- threshold reached outside cooldown -> `fired`;
- repeated threshold event inside cooldown -> `suppressed_cooldown`;
- healthy/sibling condition after an active alert -> `recovered`;
- unrelated valid generic event -> `ignored`.

Cache kinds are mutually exclusive for a canonical PR-101 cache event. Switching
from one cache failure profile to another first recovers an active sibling and
then evaluates the new signal.

Equal timestamps are allowed and serialized by one `RLock`; decreasing timestamps
for the same retained signal fail closed as out-of-order.

## Retention and capacity

Inactive state older than configured retention is pruned. Active state is not
pruned while its cooldown is still live. Capacity is structurally four, exactly
the number of supported global kinds, so no issuer/cardinality dimension can
create unbounded state.

`clear()` removes all process-local state. Restart starts empty. No state is
written to disk or a database.

## Safe outputs

`ExpertRaRatingActionsAlertEvaluationV1` contains only:

- evaluation timestamp;
- fixed global scope;
- source event name;
- disposition;
- one of four global operational kinds;
- operational severity;
- consecutive count and threshold;
- cooldown remaining seconds;
- fixed/allowlisted error code.

It contains no correlation id, source metrics, issuer/rating/action/release data,
account data or upstream exception text. Recovery removes the prior error code.

## No delivery or execution

PR-102 adds no:

- logger/emitter invocation;
- webhook, email, Telegram or pager transport;
- FastAPI route, GPT Action or public response field;
- startup/background task;
- broker SDK call;
- order, cancellation, transfer or withdrawal method;
- margin, short or derivative execution.

`app:app`, exactly 14 read-only GET Actions and `trading_methods=false` remain
unchanged.

## Tests

Focused tests cover:

- exact four-kind/global policy shape;
- validator-bypassed policy rejection;
- threshold, fire, cooldown and recovery;
- cache unavailable/hidden-stale/stale/fresh-fallback mapping;
- sibling recovery before a new cache condition;
- healthy and unrelated-event behavior;
- forged known-event profiles and sensitive flags;
- out-of-order rejection and retention pruning;
- impossible evaluation-state rejection;
- deterministic concurrent same-timestamp serialization;
- serialized alert-output absence of issuer/rating/action/release/publication data;
- stable package exports;
- absence of route, notification and broker-write surfaces.

## Next step

Only after PR-102 passes Regression Shield on its exact head and squash-merges may
PR-103 add a bounded deterministic fired/recovered terminal evidence lifecycle.
That evidence must remain global, retain only operational alert identity/state,
use bounded retention/capacity, and add no external transport or trading surface.
