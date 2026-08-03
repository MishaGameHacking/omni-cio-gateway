# Omni-CIO v9 — Investment Policy Statement Engine

Status: **WP2 implementation contract**  
Parent program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`  
Protected baseline: **Omni-CIO v8.6.1**

## 1. Purpose

WP2 adds a versioned Investment Policy Statement (IPS) for owner-specific portfolio objectives and constraints.

The IPS is not a trade authorization and does not replace the existing non-personalized `ConservativeRiskPolicyV1`. The conservative baseline remains available as a safe analytical fallback. Personal portfolio sizing is allowed only when the IPS is complete, effective, current and sufficiently owner-confirmed.

## 2. Professional design principles

The engine follows established portfolio-governance principles:

- investment objectives and constraints are explicit before recommendations/actions;
- risk willingness and risk capacity are separate concepts;
- horizon, liquidity, taxes/account context and portfolio-wide concentration matter to suitability;
- policy is reviewed regularly rather than inferred indefinitely from old context;
- diversification and risk limits are evaluated at total-portfolio level;
- missing owner constraints are not replaced by model guesses.

External design references used for engineering review include CFA-style IPS practice and the requirement to establish client objectives/constraints before portfolio action.

## 3. Required owner policy dimensions

A sizing-ready policy records:

- primary objective;
- time horizon;
- explicit liquidity reserve in base currency;
- risk willingness;
- risk capacity;
- maximum acceptable drawdown;
- maximum position, economic-group, sector and currency exposures;
- allowed markets and instrument classes;
- any explicit prohibited markets and instrument classes;
- tax-constraint review status;
- account type;
- rebalancing band;
- minimum credit quality + rating scale whenever bonds are allowed.

The engine deliberately does not infer:

- reserve = zero;
- risk tolerance from age;
- risk capacity from portfolio size alone;
- allowed/prohibited markets or classes from current holdings;
- a credit floor from the instruments already owned.

## 4. Provenance

Each required field has at most one `PolicyFieldProvenanceV1` record.

Provenance identifies whether the value came from:

- owner input;
- verified account data;
- a system safe default.

For personal sizing, owner preference/constraint fields must come from `OWNER_INPUT` and be owner-confirmed. A system safe default may remain useful as a separate safety fallback but cannot satisfy a personal-policy field. Account type is the narrow exception: verified account data may satisfy it without redundant owner confirmation; owner-supplied account type still requires owner confirmation.

Material deny constraints are policy fields too. If prohibited markets or prohibited instrument classes are configured, they require their own acceptable provenance and owner confirmation.

A value with missing or unacceptable provenance is not sizing-ready.

## 5. Lifecycle and annual review

Each IPS has:

- stable `policy_id`;
- monotonically increasing integer-like version;
- creation/effective timestamps;
- review due timestamp;
- optional previous version reference;
- lifecycle: draft, active or superseded.

The review interval cannot exceed 366 days. A policy is fail-closed for personal sizing when:

- lifecycle is not active;
- it is not effective yet;
- annual review is due/overdue;
- a required field is missing;
- provenance is missing;
- provenance source is unacceptable for personal policy;
- an owner-required field is not confirmed.

## 6. Deterministic fingerprint

`policy_fingerprint_sha256()` hashes the canonical immutable policy payload using stable JSON ordering. Semantically set-like collections such as allowed/prohibited markets and instrument classes are normalized. Provenance rows are sorted by policy field before hashing.

Later immutable portfolio plans must reference the exact `policy_id`, version and SHA-256 fingerprint used for their calculations. Any material policy change therefore changes the reference.

## 7. Constraint consistency

The contract rejects contradictory or structurally unsafe policy values:

- a market cannot be both allowed and prohibited;
- an instrument type cannot be both allowed and prohibited;
- liquidity reserve currency must equal base currency;
- group/sector caps cannot be smaller than a single-position cap;
- rebalancing band cannot exceed 50%;
- bond permission requires both a rating floor and named rating scale;
- supersession must move forward in version number;
- timestamps must be timezone-aware;
- non-owner provenance cannot assert `owner_confirmed=true`.

Before-normalization validators accept raw Pydantic input only after explicit collection type narrowing; scalar strings/numbers are rejected instead of being accidentally iterated into policy collections.

No raw notes/free-text policy field is provided. Full numeric account identifiers are rejected from provenance source IDs.

## 8. Execution boundary

IPS cannot enable:

- margin;
- short sales;
- withdrawals;
- transfers;
- autonomous real-money execution.

These are `Literal[False]` contract fields. WP2 adds no broker call, no public route, no OpenAPI operation, no Render secret and no GPT Editor change.

Real execution remains governed by the proven v8.6.1 server-side proposal/confirmation/preflight/idempotency/reconciliation contract.

## 9. Migration / rollback

WP2 is internal/additive.

Rollback means reverting the new policy contract/engine and keeping the existing conservative risk policy and v8.6.1 production behavior unchanged. No durable broker-execution state is migrated by WP2.

## 10. Exit gate

WP2 is complete only when:

1. versioned IPS contract and deterministic evaluator exist;
2. incomplete policies remain drafts and block personal sizing;
3. no zero-reserve or risk-tolerance inference occurs;
4. provenance/source/owner-confirmation gates are tested;
5. allow/deny constraint contradictions are rejected;
6. annual review and supersession are tested;
7. policy fingerprint is stable and mutation-sensitive;
8. protected execution permissions cannot be enabled;
9. ruff, mypy, full tests and exact-head Regression Shield are green;
10. squash merge completes and epic #176 marks WP2 complete.
