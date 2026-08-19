# FL-022 — Pre-CI formatting must execute the exact pinned formatter over the complete changed Python surface

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR PR #336; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-19**  
WP / PR / reference: **WP22A Phase 2 Product-auth / tenant-security correction / PR #336**

## Symptom / failing gate

On exact PR head `ef9272e4c51988d0bf15795bec6d74a89ed3647a`, focused **V10 WP22A Phase 2 Product Auth Tenant Audit #14** completed exact checkout and the hash-locked toolchain install. `ruff check` passed, but `ruff format --check` failed on three changed Python files:

- `scripts/rehearse_v10_wp22a_phase2_tenant_security.py`;
- `tests/test_v10_wp22a_phase2_source_contract.py`;
- `tests/test_v10_wp22a_product_identity.py`.

The failure was formatter-only. Because the focused workflow is fail-fast, mypy, pytest, PostgreSQL tenant-security rehearsal, inherited WP13 recovery rehearsal and downstream guards did not execute and their skipped states are not PASS evidence.

## Root cause

The Phase-2 pre-CI review covered security semantics, migration/RLS behavior, API tenant authority and inherited consumers, but it did not execute the **exact pinned Ruff formatter check against the complete changed Python file set** before declaring the branch ready for another expensive self-hosted exact-head cycle.

`ruff check` and `ruff format --check` are separate gates. A lint-clean file is not necessarily formatter-clean. The repository workflow correctly treated formatting drift as RED.

## Blast radius searched

The formatter output identified exactly three files. The correction applies only Ruff-required source layout changes and does not alter:

- identity binding semantics;
- registration enablement;
- server-side session authority;
- tenant scope;
- PostgreSQL RLS policy;
- broker authority;
- public/provider activation;
- protected V9 rollback.

The focused workflow already runs formatting before mypy, pytest and PostgreSQL rehearsal, so no gate was disabled or reordered to hide the failure.

## Corrective change

Apply the exact formatter-required representation to all three reported files and start a new exact-head cycle. Do not reuse any prior GREEN evidence after the formatting commits.

The formatter itself remains pinned by the repository's hash-locked development dependency set; no dependency/version change is required for this correction.

## Permanent regression / guard

The dedicated Phase-2 workflow retains both independent early checks:

1. `ruff check` for lint/static rule compliance;
2. `ruff format --check` for canonical formatting.

Both must pass before mypy, pytest or the PostgreSQL rehearsal can be credited.

## Future prevention rule

Before declaring a Python-bearing PR pre-CI ready, execute the repository-pinned formatter check against the **same complete file set that the focused workflow will inspect**, not merely a visual/manual style review or linter run.

For a changed Python surface, the cheap local/preflight order is:

`pinned ruff check -> pinned ruff format --check -> type/unit checks -> expensive self-hosted integration/recovery gates`.

A formatter RED is still RED even when behavior is unchanged. The correct response is to apply the formatter and rerun exact-head verification, not weaken or remove the format gate.

## Dependency/tooling knowledge change

Ruff's linter and formatter are separate commands. The formatter's `--check` mode intentionally returns non-zero when any file would be reformatted. Preflight must therefore exercise both commands with the repository-pinned Ruff version and the focused workflow's exact file surface.
