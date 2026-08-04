# WP14 — Decision Journal Threat Model

## Protected assets

- immutable decision-time evidence and expectation bindings;
- realized outcome evidence;
- evaluation outputs and benchmark availability state;
- sanitized offline replay datasets;
- durable journal integrity metadata and journal HMAC secret;
- the existing v8.6.1 real-money execution boundary and the applied GPT configuration.

## Threats and controls

### Hindsight rewriting

Threat: after observing the outcome, a historical decision or expectation is edited to appear better calibrated.

Controls: strict frozen contracts, canonical record hashes, append-only journal API, no update/delete method, and separate outcome/evaluation records. A conflicting payload under an existing immutable identity fails closed.

### Forged counterfactuals

Threat: a `NO_ACTION` or policy benchmark is invented despite insufficient historical evidence.

Controls: benchmark values require a matching source SHA. Missing benchmark evidence remains `UNAVAILABLE`; the evaluator does not estimate a replacement.

### External-flow attribution error

Threat: deposits or withdrawals are mistaken for investment performance.

Control: period result subtracts net external flow from ending-minus-starting value. The source outcome remains separate and auditable.

### Evaluation rebinding

Threat: an evaluation is attached to a different revised decision/outcome.

Controls: evaluation stores exact decision and outcome record hashes; both in-memory and durable journals validate those bindings before append and during integrity checks.

### Durable-state tamper

Threat: Redis row or metadata contents are edited without the journal secret.

Controls: journal-specific HMAC for each row and authenticated metadata, atomic append CAS, exact idempotent replay semantics, strict HTTPS Upstash transport and fail-closed decoding.

### Storage-administrator rollback

Threat: an actor with full datastore administration restores an older internally valid snapshot.

Control boundary: HMAC/CAS detects unauthorized content mutation and inconsistent counts but cannot create an external monotonic timeline inside the same datastore. Operational backups/access controls and recovery review are required. WP14 does not claim rollback protection beyond the available infrastructure.

### Privacy leakage through replay datasets

Threat: account identifiers, broker payloads or secrets are exported into offline evaluation fixtures.

Controls: replay contracts explicitly assert absence of full account identifiers, raw private payloads, secrets and production-write capability. Production-derived replay source requires explicit sanitization confirmation. Synthetic/fake-broker data is the default evaluation source.

### Self-modifying production behavior

Threat: evaluation results automatically rewrite prompts, rules, owner policy, model configuration or deployed behavior.

Controls: regression result has `production_change_applied=false` and `self_modification_authorized=false`. A candidate can only become ready for review. Production changes require normal reviewed repository/config delivery; Custom GPT remains v8.6.1 until WP15.

### Execution authority escalation

Threat: WP14 obtains broker mutation access while evaluating decisions.

Controls: permanent repository guard rejects imports/calls from real trading, Sandbox and broker mutation APIs. The package has no execution endpoints and no broker token configuration.

## Failure posture

WP14 fails closed on malformed hashes, timezone ambiguity, identity conflicts, missing source bindings, journal integrity errors, durable storage failures, incomplete replay case coverage and unsafe unsanitized production dataset export.
