# V10 Engineering Failure Learning Ledger — FL115

## Failure class

`EXECUTION_LEDGER_MACHINE_MARKER_DROPPED_DURING_REFRESH`

## Evidence

Exact PR head `902fca16fb83b1d72dd8a2ff9b8edabf3fe7a8ee` completed repository policy, compile, Ruff, formatting and mypy successfully, then the protected regression suite reported two failures with one shared cause:

- `CLOUDFLARE_CANDIDATE_BRANCH_LEDGER_INVALID`;
- Green Checkpoint governance reported the branch execution ledger missing the exact marker `Green Checkpoint verification`.

All other observed current-head PR workflow lanes completed successfully except the owning Self-Hosted Windows CI and Engineering Governance lanes that consumed the same missing marker. Exact-head Sonar remained successful and the real Cloudflare staging Workers Build completed successfully.

## Root cause

The branch execution ledger was refreshed to restore current CF-D evidence, but its existing machine-consumed section heading `Green Checkpoint verification` was renamed to the semantically similar `Green Checkpoint history`. The documentation remained understandable to a human reviewer, but two accepted governance consumers intentionally require the exact marker and therefore failed closed.

## Blast radius

The failure is confined to the branch-scoped execution-ledger compatibility contract. No runtime source, provider authority, database state, secret custody, deployment path or broker authority was changed by the heading rename. The directly coupled consumers are `scripts/check_v10_cloudflare_candidate_delivery.py` and the Green Checkpoint governance guard exercised by `tests/test_v10_green_checkpoint_ci_repair.py`.

## Correction

Restore the canonical `Green Checkpoint verification` marker while keeping the refreshed evidence underneath it. Do not weaken the consumers or replace exact marker checks with permissive matching merely to obtain GREEN.

The existing candidate-delivery and Green Checkpoint tests remain the deterministic regression guards for this compatibility boundary.

## Prevention law

When updating tracked governance/status documents that are consumed by repository guards, inspect their direct consumers before renaming or restructuring canonical machine-read markers. Human-readable semantic equivalence does not replace a source-controlled compatibility contract.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write OFF; transfer, withdrawal, margin, leverage and uncovered-short authority remain forbidden; no Web Visual, Telegram/VK, AI/Cortex, D1 or speculative Hyperdrive scope is introduced.
