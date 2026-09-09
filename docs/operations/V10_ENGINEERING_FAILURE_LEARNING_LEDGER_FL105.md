# V10 Engineering Failure Learning Ledger — FL105

Date: 2026-09-09  
Scope: PR #471 / Amendment 16 Green Checkpoint & Targeted CI Repair adoption  
Authority: Amendment 8 + Amendment 12 + proposed Amendment 16

## Symptom / failing gates

During exact-head certification of PR #471, fail-closed verification exposed four repository-content defects while the Green Checkpoint repair loop was being exercised:

1. `check_v10_green_checkpoint_ci_repair.py` rejected `scripts/check_v10_pr_external_review_gate.py` because the deterministic guard required literal zero-finding markers while the reviewed Sonar gate had been refactored to construct those failure messages dynamically.
2. After that repair, `check_v10_cloudflare_candidate_delivery.py` rejected the current Cloudflare branch Execution Ledger because its coupled ledger guard still required the superseded `HEAD FREEZE` marker instead of Amendment-16 Green Checkpoint state markers.
3. After restoring static Sonar markers, `Self-Hosted Windows CI` rejected the replacement checkpoint because the final one-line failure-message edit had not been passed through canonical Ruff formatting before publication.
4. After formatting was restored, protected Regression Shield found nine failures in `tests/test_v10_engineering_governance.py`: the engineering-governance refactor had renamed the protected `validate_contract` orchestrator to `_validate_contract` and merged focused validator interfaces that regression tests intentionally treat as repository contracts.

None of these failures authorized a same-SHA blind rerun. Each was a repository-content defect and therefore required a replacement SHA and fresh certification.

## Root cause

`GOVERNANCE_SUPERSESSION_PRODUCER_CONSUMER_DRIFT`

The Amendment-16 update correctly changed canonical governance producers — machine contracts, live guidance, templates, runbooks and central governance checks — but the first implementation pass did not completely bind every downstream deterministic consumer to the new representation. A later repair also proved that replacement-head publication must repeat cheap preflight after every content edit and must preserve stable validator APIs consumed by the regression suite.

The defect sub-classes were:

- **static-marker drift**: a guard asserted source evidence by literal marker while the producer generated the same semantic message from a variable;
- **superseded-consumer drift**: a pre-existing Cloudflare candidate guard consumed the branch Execution Ledger and still encoded the old `HEAD FREEZE` vocabulary;
- **post-repair preflight drift**: a content repair was semantically correct but was published without re-running the canonical formatter check on the touched Python file;
- **validator API compatibility drift**: refactoring preserved broad validation intent but removed the established `validate_contract` callable and focused helper names enforced by regression tests.

## Blast radius / analogous search

Reviewed surfaces included:

- Amendment-16 contract, runbook and central governance guard;
- `AGENTS.md`, `CONTRIBUTING.md`, README, GPT/Copilot instructions, PR/WP/System-Update templates and the active Cloudflare Execution Ledger;
- `scripts/check_v10_integrated_system_update_governance.py` historical Amendment-12 marker validation;
- `scripts/check_v10_cloudflare_candidate_delivery.py` as a live consumer of the active Cloudflare ledger;
- `scripts/check_v10_engineering_governance.py` plus its full regression-test consumer surface;
- exact-head Sonar enforcement and its tests;
- Ruff formatting on changed Python governance/check/test surfaces;
- repository search for remaining `HEAD FREEZE` references, distinguishing historical amendment evidence from active operational consumers.

Historical Amendment-12 text is preserved as historical authority evidence. Active live guidance/consumers must follow Amendment 16 once it is accepted.

## Why preflight missed it

The first preflight concentrated on the new law's owning files and live-guidance surfaces. It did not execute every already-existing downstream guard that parses those surfaces before the first exact-head governance cycle. The Sonar-message refactor also preserved runtime semantics but unintentionally removed the exact static source marker consumed by the new self-check.

The formatting RED happened because a replacement edit was published after semantic review but before `ruff format --check` was repeated. The later Regression Shield RED showed that running only the governance script itself was insufficient: its public/internal validator interface is also consumed structurally by repository regression tests.

These failures are precisely the classes the Green Checkpoint law is intended to surface before dependent work proceeds.

## Corrective change

- Keep explicit static zero-finding message constants in `check_v10_pr_external_review_gate.py` while retaining the same fail-closed Sonar semantics.
- Update `check_v10_cloudflare_candidate_delivery.py` to require `Green Checkpoint verification`, `RED_REPAIR_ONLY` and `CERTIFIED_GREEN` from the active Cloudflare branch ledger instead of the superseded `HEAD FREEZE` marker.
- Apply canonical Ruff formatting before publishing replacement checkpoints.
- Restore `validate_contract` as the decomposed engineering-governance orchestrator and restore the focused validator interfaces expected by regression tests, while keeping Amendment-16 live-surface checks active.
- Preserve all CF-C/CF-D provider, secret, tenant, rollback, production and broker/Real-money authority guards unchanged.
- Treat every content repair as a replacement checkpoint SHA; prior final evidence is stale.

## Permanent regression / guard

- `V10 Engineering Governance` executes the Green Checkpoint guard and Cloudflare candidate-delivery guard in the same exact-head job.
- `check_v10_green_checkpoint_ci_repair.py` verifies active guidance has Amendment-16 markers and rejects known superseded operational markers.
- `tests/test_v10_cloudflare_candidate_provider.py::test_repository_candidate_contract_is_valid` executes the candidate guard against the real repository ledger.
- `tests/test_v10_engineering_governance.py` protects the decomposed `validate_contract` interface, focused validator calls, negative policy mutations and authority invariants.
- `Self-Hosted Windows CI` runs canonical Ruff lint/format and mypy before protected Regression Shield/security.
- Exact-head Sonar enforcement still requires Quality Gate success, zero new issues, zero Security Hotspots and zero annotations/new findings.

## Future prevention rule

A governance supersession must audit **both producers and consumers** before publication. Search for superseded vocabulary and callable interfaces across live docs, templates, workflows, scripts and tests; classify historical evidence separately; then run every deterministic guard and regression test that parses or imports a changed governance surface.

If a source guard relies on literal source evidence, keep that evidence static and explicit or replace the check with a semantic executable assertion. If a validator callable/helper is already consumed by tests or other scripts, treat its name/signature/decomposition as a compatibility contract unless producer and consumers are intentionally migrated together.

After **every** content-changing repair, repeat the smallest applicable canonical format/lint/type/parser/unit preflight on the touched surface before publishing the replacement SHA. A one-line repair does not inherit preflight evidence from the prior SHA.

## Dependency / tooling knowledge change

Marker-based governance validators and imported validator functions are interface consumers. Their expected vocabulary and callable boundaries are part of the repository contract and must be migrated atomically with the documents, ledgers or scripts they parse. Formatter conformance is likewise part of the exact-head repository contract, not cosmetic post-processing.
