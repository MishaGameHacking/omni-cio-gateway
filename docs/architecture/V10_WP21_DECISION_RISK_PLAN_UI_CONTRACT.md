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

`/risks`, `/decisions` and `/plans` use the same canonical payload and differ only in page focus. This avoids three competing versions of the same decision state.

The local API is:

`GET /api/v10/web/decision-plan`

It is session-scoped, tenant-scoped and no-store.

## States

- `EMPTY`: no canonical decision is stored;
- `PARTIAL`: canonical decision exists but an actionable decision has no valid exact plan;
- `READY`: canonical binding is valid and unexpired;
- `EXPIRED`: exact immutable plan is retained for audit but its approval subject is no longer valid;
- `INVALID`: hash/schema/model/binding semantics fail closed.

The UI never converts `PARTIAL`, `EXPIRED` or `INVALID` into optimistic success.

## MAIN_DECISION

The large `MAIN_DECISION` label is a deterministic presentation projection documented in `V10_WP21_EXECUTION_CONTRACT.md`. It is not a replacement for `DecisionAction`, Strategy or Optimizer logic.

If the projection cannot be derived without guessing, it is `UNAVAILABLE` and the response is not `READY`.

## Exact mathematics

When a valid immutable plan is available, the screen renders source values without recomputation:

- portfolio/cash before and after;
- concentration before and after;
- policy compliance and risk vectors;
- target lots and target weights;
- exact plan legs;
- reference clean unit values;
- gross/settlement turnover;
- accrued interest;
- commission and estimated sell tax;
- cash delta and staging days.

The UI must not present these values as model forecasts.

## Alternatives and evidence

Alternatives come from the non-preferred canonical `DecisionOptionV1` objects. Their canonical title, rationale, action, confidence, blockers and review conditions are displayed as supplied.

Evidence comes from canonical `DecisionEvidenceV1` records. React text rendering remains the only presentation path; external/source text is never executed as markup or instruction.

## Immutable approval subject

The UI may reveal the existing `owner_approval_phrase` only when:

- the exact `PortfolioPlanV1` validates including its canonical internal SHA;
- the plan requires approval;
- the plan has not expired.

The zone is permanently labeled:

`FUTURE OWNER CONFIRMATION SUBJECT · PREVIEW ONLY`

It contains no active confirmation button and returns `can_approve=false`.

A materially altered plan cannot keep the old approval subject because `PortfolioPlanV1` validates its canonical payload hash and exact phrase binding.

## Security and privacy

- no full broker account identifier is needed or returned;
- no broker token enters this surface;
- no browser Web Storage is used;
- no raw PostgreSQL content blob is returned;
- no public ingress is added;
- no order/trade/transfer endpoint is added;
- `execution_authorized=false` and `trading_methods=false` remain explicit.

## Browser evidence

Synthetic Playwright evidence must show a long-form decision page containing:

- deterministic `MAIN_DECISION`;
- before/after risk;
- exact target lots;
- exact cost/cash values;
- alternatives;
- preview-only immutable approval subject;
- no approval action.

A separate browser test must show that an invalid plan has no approval-subject zone.
