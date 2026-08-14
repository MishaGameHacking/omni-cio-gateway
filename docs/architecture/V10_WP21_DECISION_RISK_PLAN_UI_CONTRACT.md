# V10 WP21 Decision / Risk / Plan UI Contract

Status: **implementation contract**

## Canonical hierarchy

The Web presentation has one authority order:

1. canonical deterministic `DecisionSetV1`;
2. exact bound immutable `PortfolioPlanV1` when the decision is actionable;
3. exact plan `risk_before` / `risk_after`, optimizer targets and rebalance legs;
4. descriptive UI labels derived deterministically from those objects.

The browser is never a financial calculator or approval authority.

## Route behavior

`/risks`, `/decisions` and `/plans` use the same canonical payload and differ only in page focus. The local API is `GET /api/v10/web/decision-plan`; it is session-scoped, tenant-scoped and no-store.

## States

- `EMPTY`: no canonical decision is stored;
- `PARTIAL`: canonical decision abstains with `WAIT_FOR_DATA`, or an actionable decision has no valid exact plan;
- `READY`: canonical binding is valid and unexpired;
- `EXPIRED`: exact immutable plan is retained for audit but its approval subject is no longer valid;
- `INVALID`: hash/schema/model/persisted-binding semantics fail closed.

The UI never converts `PARTIAL`, `EXPIRED` or `INVALID` into optimistic success.

## MAIN_DECISION

The large `MAIN_DECISION` label is a deterministic presentation projection documented in `V10_WP21_EXECUTION_CONTRACT.md`; it does not replace `DecisionAction`, Strategy or Optimizer logic.

`WAIT_FOR_DATA` is displayed as `NO_ACTION` but remains `PARTIAL`. Any projection that would require guessing is `UNAVAILABLE` and cannot be `READY`.

## Exact mathematics

When a valid immutable plan exists, the screen renders accepted source values without recomputation: portfolio/cash before and after, concentration/policy/risk vectors, target lots/weights, exact legs, reference values, turnover, accrued interest, commission/tax, cash delta and staging days. These are not presented as model forecasts.

## Durable identity binding

Before a plan is rendered as current, backend verifies:

- exact tenant / portfolio / canonical-policy / snapshot scope from durable relations;
- plan `portfolio_snapshot_sha256` equals snapshot `source_payload_sha256`;
- plan source policy id equals durable policy `source_policy_id`;
- plan `created_at` equals persisted plan `created_at`;
- outer content SHA/schema and Pydantic contracts validate;
- internal canonical plan SHA and approval phrase recompute correctly.

The durable decision `decided_at` is shown as audit metadata and is not incorrectly required to equal the DecisionSet source-retrieval timestamp.

A mismatch is `INVALID`, never a degraded-but-approvable plan.

## Alternatives and evidence

Alternatives come from non-preferred canonical `DecisionOptionV1` objects; evidence comes from canonical `DecisionEvidenceV1`. React text rendering is the presentation path, so source text never becomes executable markup or instruction.

## Immutable approval subject

The UI may reveal `owner_approval_phrase` only when the exact `PortfolioPlanV1` and its durable bindings validate, approval is required, and the plan is not expired.

The zone is permanently labeled `FUTURE OWNER CONFIRMATION SUBJECT · PREVIEW ONLY`, contains no confirmation action and returns `can_approve=false`. A material mutation cannot retain the old approval subject because canonical plan hash/phrase validation fails.

## Security and privacy

No full broker account identifier or broker token is required; no browser Web Storage/raw PostgreSQL blob/public ingress/order/trade/transfer endpoint is added; `execution_authorized=false` and `trading_methods=false` stay explicit.

## Browser evidence

Synthetic Playwright evidence must show deterministic `MAIN_DECISION`, before/after risk, exact target lots/cost/cash values, alternatives, preview-only immutable approval subject, and no approval action. A separate invalid-plan browser case must have no approval-subject zone.
