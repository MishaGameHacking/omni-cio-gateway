# FL-168 — Published governance checkpoints must run Ruff formatting before remote certification

Date: 2026-09-24  
WP / PR / reference: TIMEWEB-PLATFORM-CONSOLIDATION / V9C-A / PR #584 / exact head `f206364279e52765891756b1ba807c1efd5c74bd`

## Symptom

`V10 Fast PR Checks` failed only at the changed-file Ruff format gate for the new
V9-to-V10 convergence guard and its regression test.

## Root cause

The V9C-A correction was published after semantic review without applying the
repository's exact Ruff formatting rules to the replacement Python files. The earlier
FL-007 class therefore recurred on newly introduced governance code.

## Blast radius

The failure was limited to formatting of
`scripts/check_v10_v9_to_v10_convergence.py` and
`tests/test_v10_v9_to_v10_convergence.py`. Engineering Governance had already passed
the convergence guard itself on the same source semantics before this format gate.

## Corrective change

Apply the exact Ruff-compatible line wrapping reported by the Fast PR gate. No
contract, authority, runtime or security behavior is changed.

## Permanent prevention rule

Every repository-changing script/governance checkpoint must include changed-file
`ruff check` and `ruff format --check` preflight before publication. A semantic-only
review is insufficient for Python checkpoint readiness.

## Dependency/tooling knowledge change

None.
