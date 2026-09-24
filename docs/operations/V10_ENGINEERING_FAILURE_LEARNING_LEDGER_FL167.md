# FL-167 — Governance guards must validate the contract representation actually emitted

Date: 2026-09-24  
WP / PR / reference: TIMEWEB-PLATFORM-CONSOLIDATION / V9C-A / PR #584 / exact head `f06ce280be49a6ef7d6075f08175469ed101e601`

## Symptom

The new V9-to-V10 convergence governance step failed with
`V9C_DOCUMENTATION_DRIFT` even though the execution ledger contained the required
V9C-A and V9C-F information.

## Root cause

The guard expected a prose marker in the form
`V9C-A / AUTHORITY_AND_INVENTORY`, while the canonical execution ledger represents
the same identity structurally as separate Markdown table columns:

`| V9C-A | AUTHORITY_AND_INVENTORY |`.

The validator therefore imposed a presentation format that the contract never required.

## Blast radius

Reviewed the new V9 convergence guard's documentation markers for the amendment,
Amendments Index, current status, execution ledger, AGENTS, README and CONTRIBUTING.
Only the execution-ledger markers used a mismatched representation. The machine
contract identity, migration inventory, merge-authority lock and protected flags were
not implicated.

## Corrective change

The guard now validates the ledger's structural table markers rather than inventing a
second prose serialization. Current status and amendment prose checks remain unchanged
because those files actually use the slash-form identity.

## Permanent regression protection

`tests/test_v10_v9_to_v10_convergence.py::V9ToV10ConvergenceGuardTests.test_current_repository_passes`
executes the guard against the repository's canonical table representation. Any future
ledger representation change must update producer and guard coherently.

## Future prevention rule

A governance verifier must validate semantic structure in the representation owned by
the producer. Do not strengthen a contract by silently requiring an alternate
human-readable serialization.

## Dependency/tooling knowledge change

None. This was a repository contract/validator mismatch, not a toolchain or provider
failure.
