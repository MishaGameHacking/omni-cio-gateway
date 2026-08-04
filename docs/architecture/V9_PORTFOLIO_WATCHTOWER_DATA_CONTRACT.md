# V9 Portfolio Watchtower — Data Contract

## Version

WP13 Watchtower contract version: `1.0`.

## Input

`WatchtowerInputV1` contains:

- timezone-aware `checked_at`;
- scheduler `delivery_id` used for transport replay protection;
- exact `portfolio_snapshot_sha256`;
- exact `PolicyReferenceV1`;
- canonical WP8 `PortfolioRiskAssessmentV1`;
- zero or more canonical WP6 `CreditPassportV1` objects;
- zero or more `MarketResearchBundleV1` objects;
- explicit source/data-quality codes;
- canonical `input_sha256`;
- hard-disabled execution fields.

Validation requires risk to bind the exact portfolio snapshot and policy. Every credit passport must bind the same policy. Duplicate credit/passport or market-bundle identities are rejected.

## Alert

`WatchtowerAlertV1` contains only decision-safe alert metadata:

- deterministic `alert_id`;
- semantic `fingerprint_sha256`;
- signal kind and existing observability severity;
- bounded subject key;
- effective timestamp;
- source/evidence SHA-256 references;
- allowlisted-style `message_code`;
- owner-attention flag;
- requested non-execution action;
- `execution_authorized=false`;
- `trading_methods=false`.

Raw source text, account identifiers and secrets are not part of the alert contract.

## Semantic fingerprint

Transport and evidence hashes are intentionally separated from signal identity.

Examples:

- rating downgrade: rating observation id + resulting rating/action;
- default: default event id + type;
- corporate event: event id + type;
- concentration: dimension + bucket + hard/soft breach identity;
- stale/unknown liquidity: stable instrument key + stale/unknown state;
- policy breach: policy fingerprint + blocker set.

This prevents repeat notification solely because a new polling run generated a new assessment SHA.

## Durable state

`WatchtowerStateV1` contains:

- stable `watch_id` derived from policy identity;
- monotonically increasing `revision`;
- initialize/update timestamps;
- current policy reference;
- last portfolio/risk/input identities;
- bounded recent delivery IDs;
- current active semantic fingerprints;
- canonical `state_sha256`;
- hard-disabled execution fields.

State update is compare-and-swap. A stale writer cannot overwrite a newer revision.

Current active fingerprints, rather than a permanent historical suppression set, are retained. When a condition resolves its fingerprint disappears; a later recurrence can therefore generate a new alert.

## Evaluation

`WatchtowerEvaluationV1` contains:

- exact input identity;
- replay flag;
- sorted emitted alerts;
- `material_change`;
- `should_notify`;
- non-execution proposed action;
- committed durable state;
- canonical evaluation SHA;
- hard-disabled execution fields.

Invariant:

`material_change == should_notify == bool(alerts)`.

A duplicate delivery is a replay and must emit zero alerts.

## Initial-baseline semantics

The first run establishes active fingerprints. Existing warning/error conditions are surfaced once; routine non-material state remains silent. This prevents a newly enabled Watchtower from hiding an active default or current material risk breach while also avoiding informational baseline spam.

## Scheduler payload

The QStash endpoint will accept a small versioned trigger envelope rather than holdings or source payloads. The trigger identifies the Watchtower job/run; the Gateway then reads fresh canonical evidence through existing read-only providers.

Scheduler request bodies and callback responses are authenticated independently. Duplicate schedule/callback deliveries remain safe because durable Watchtower state is idempotent.

## No real-money authority

No Watchtower input, state, alert or evaluation can authorize an order. Any proposed plan produced downstream remains an immutable WP11 artifact and requires the existing WP12 owner-confirmed execution protocol.
