# V10 Engineering Failure Learning — FL163

Failure class: `CF_D_CLOSEOUT_COUPLED_LEDGER_CONSUMER_DRIFT`

Date: 2026-09-18

Scope: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / accepted-state closeout`

## Observed failure

Focused closeout PR #548 correctly converted the Cloudflare execution ledger from the
active branch-local state to an accepted historical record. On replacement exact head
`93babb6fb86e6df670eddd45cce420bc2e494cc6`, V10 Engineering Governance #1611
passed the Green Checkpoint compatibility guard and then stopped at:

`CLOUDFLARE_CANDIDATE_BRANCH_LEDGER_INVALID`

The failing consumer was
`scripts/check_v10_cloudflare_candidate_delivery.py::_validate_ledger()`.

## Root cause

The candidate-delivery guard was a direct machine consumer of the same execution ledger,
but its lifecycle contract still required the old active-state header:

`BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY`

That requirement was correct while the integrated update was executing, but became stale
once accepted production evidence allowed the ledger itself to transition to:

`ACCEPTED COMPLETE / HISTORICAL EXECUTION RECORD — NOT CURRENT-STATE AUTHORITY`

The closeout updated the producer (the ledger) and the main documentation/governance
consumers, but the CF-C candidate guard remained coupled to the old producer lifecycle.

## Blast radius

The defect is limited to deterministic repository governance compatibility. It does not
change candidate workflow behavior, Cloudflare authority, Neon/PostgreSQL state, provider
secret custody, Custom Domain state, public capability activation, broker authority or
Real execution.

Directly coupled surfaces reviewed:

- Cloudflare execution ledger;
- Green Checkpoint guard;
- Cloudflare candidate-delivery guard;
- integrated public-product governance guard;
- documentation-consistency guard;
- candidate-provider regression suite;
- closeout regression suite.

Repository search found no other live script consumer requiring the old branch-local
header.

## Permanent correction

The candidate-delivery guard now validates the accepted historical lifecycle state
instead of forcing the ledger back to a false active state. It still requires:

- the canonical integrated update and historical branch identity;
- dashboard issue #412;
- accepted Production Release #78 evidence;
- CF-A/CF-B/CF-C/CF-D markers;
- `Green Checkpoint verification`;
- historical `RED_REPAIR_ONLY` and `CERTIFIED_GREEN` vocabulary;
- `PUBLIC_MULTI_USER_ENABLED=false`.

The guard is not removed or weakened; its expected producer lifecycle is advanced to the
truthful accepted state.

A deterministic closeout regression calls the candidate ledger validator against the
repository state so future closeout/status edits cannot silently break this coupled
consumer again.

## Acceptance requirement

All earlier exact-head evidence is obsolete after this content-changing repair.
Replacement exact-head DRAFT checks, Sonar/security/review evidence, READY
recertification when applicable, squash merge and exact-new-main post-merge acceptance
remain mandatory.
