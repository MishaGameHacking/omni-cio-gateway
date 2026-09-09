# V10 Engineering Failure Learning Ledger — FL105

Date: 2026-09-09  
Scope: PR #471 / Amendment 16 Green Checkpoint & Targeted CI Repair adoption  
Authority: Amendment 8 + Amendment 12 + proposed Amendment 16

## Symptom / failing gates

During exact-head certification of PR #471, `V10 Engineering Governance` exposed two successive fail-closed defects after the new Green Checkpoint law itself and exact-head Sonar review had already passed:

1. `check_v10_green_checkpoint_ci_repair.py` rejected `scripts/check_v10_pr_external_review_gate.py` because the deterministic guard required literal zero-finding markers while the reviewed Sonar gate had been refactored to construct those failure messages dynamically.
2. After that repair, `check_v10_cloudflare_candidate_delivery.py` rejected the current Cloudflare branch Execution Ledger because its coupled ledger guard still required the superseded `HEAD FREEZE` marker instead of Amendment-16 Green Checkpoint state markers.

Neither failure authorized a same-SHA blind rerun. Both were repository-content defects and therefore required replacement SHAs and fresh certification.

## Root cause

`GOVERNANCE_SUPERSESSION_PRODUCER_CONSUMER_DRIFT`

The Amendment-16 update correctly changed canonical governance producers — machine contracts, live guidance, templates, runbooks and central governance checks — but the first implementation pass did not completely bind every downstream deterministic consumer to the new representation.

The two sub-classes were:

- **static-marker drift**: a guard asserted source evidence by literal marker while the producer generated the same semantic message from a variable;
- **superseded-consumer drift**: a pre-existing Cloudflare candidate guard consumed the branch Execution Ledger and still encoded the old `HEAD FREEZE` vocabulary.

## Blast radius / analogous search

Reviewed surfaces included:

- Amendment-16 contract, runbook and central governance guard;
- `AGENTS.md`, `CONTRIBUTING.md`, README, GPT/Copilot instructions, PR/WP/System-Update templates and the active Cloudflare Execution Ledger;
- `scripts/check_v10_integrated_system_update_governance.py` historical Amendment-12 marker validation;
- `scripts/check_v10_cloudflare_candidate_delivery.py` as a live consumer of the active Cloudflare ledger;
- exact-head Sonar enforcement and its tests;
- repository search for remaining `HEAD FREEZE` references, distinguishing historical amendment evidence from active operational consumers.

Historical Amendment-12 text is preserved as historical authority evidence. Active live guidance/consumers must follow Amendment 16 once it is accepted.

## Why preflight missed it

The first preflight concentrated on the new law's owning files and live-guidance surfaces. It did not execute every already-existing downstream guard that parses those surfaces before the first exact-head governance cycle. The Sonar-message refactor also preserved runtime semantics but unintentionally removed the exact static source marker consumed by the new self-check.

This is precisely the class of failure the Green Checkpoint law is intended to surface before dependent work proceeds.

## Corrective change

- Keep explicit static zero-finding message constants in `check_v10_pr_external_review_gate.py` while retaining the exact same fail-closed Sonar semantics.
- Update `check_v10_cloudflare_candidate_delivery.py` to require `Green Checkpoint verification`, `RED_REPAIR_ONLY` and `CERTIFIED_GREEN` from the active Cloudflare branch ledger instead of the superseded `HEAD FREEZE` marker.
- Preserve all CF-C/CF-D provider, secret, tenant, rollback, production and broker/Real-money authority guards unchanged.
- Treat every content repair as a replacement checkpoint SHA; prior final evidence is stale.

## Permanent regression / guard

- `V10 Engineering Governance` executes the Green Checkpoint guard and the Cloudflare candidate-delivery guard in the same exact-head job.
- `check_v10_green_checkpoint_ci_repair.py` verifies active guidance has Amendment-16 markers and rejects known superseded operational markers.
- `tests/test_v10_cloudflare_candidate_provider.py::test_repository_candidate_contract_is_valid` executes the candidate guard against the real repository ledger.
- Exact-head Sonar enforcement still requires Quality Gate success, zero new issues, zero Security Hotspots and zero annotations/new findings.

## Future prevention rule

A governance supersession must audit **both producers and consumers** before publication. Search for the superseded vocabulary across live docs, templates, workflows, scripts and tests; classify historical evidence separately; then run every deterministic guard that parses a changed governance surface.

If a source guard relies on literal source evidence, keep that evidence static and explicit or replace the check with a semantic executable assertion. Do not allow a formatting/refactor-only change to silently invalidate the machine governance contract.

## Dependency / tooling knowledge change

Marker-based governance validators are interface consumers. Their expected vocabulary is part of the repository contract and must be migrated together with the documents or ledgers they parse.
