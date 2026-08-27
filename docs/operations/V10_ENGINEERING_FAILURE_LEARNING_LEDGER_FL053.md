# FL-053 — Failure-learning entries are append-only and IDs must be allocated from accepted repository state

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR AMENDMENT 13; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-27**  
WP / PR / reference: **Amendment 13 governance / PR #395 / correction head `48dc497c7bd738536ddc8b2e68834ee3a16cf405`**

## Symptom / failing gate

After the stale current-status consumer correction had completed a full safe DRAFT batch with all applicable repository workflows `success`, final diff review found that the new failure-learning document had accidentally reused the already-occupied path `docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER_FL046.md`.

The accepted `FL-046` records the earlier WP22A Phase 5 HTTPX cookie-scope lesson. Reusing that path replaced historical engineering memory in the branch even though the new lesson was unrelated. The defect was caught before READY or merge and therefore never became accepted main authority.

## Root-cause analysis

The correction created a new additive failure-learning entry from remembered numbering instead of enumerating the current accepted `docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER_FLNNN.md` namespace first.

Because Git treats a path replacement as an ordinary file modification, neither the focused semantic guard nor the full Regression Shield could infer that the path was intended to be append-only historical memory. Full diff review against the accepted base exposed the unintended overwrite.

## Blast radius searched

The repository operations directory was enumerated at the accepted branch baseline. Existing additive entries occupy `FL019` through `FL051`; `FL052` is the first free ID for the superseded-current-status lesson and `FL053` is the next free ID for this process lesson.

The accepted `FL046` blob SHA is `6ffaee0778cd4faf94dec3d9586fe551597f3869` and is restored exactly. No other pre-existing failure-learning file is modified by this correction.

## Why preflight missed it

The semantic correction was reviewed for test behavior, governance authority and Regression Shield coverage, but the failure-learning filename was treated as a documentation detail. The repository already contained more additive FL files than the remembered sequence used while composing the correction.

## Corrective change

The branch now:

1. restores `V10_ENGINEERING_FAILURE_LEARNING_LEDGER_FL046.md` to the exact accepted blob;
2. records the superseded-current-status consumer lesson as new `FL052`;
3. records this append-only namespace lesson as new `FL053`;
4. keeps historical entries byte-identical unless an explicit future correction is separately justified and reviewed.

## Permanent regression / guard

For every future additive failure-learning write, preflight must enumerate the accepted `V10_ENGINEERING_FAILURE_LEARNING_LEDGER_FLNNN.md` paths and allocate an unused ID from repository state before creating the file. Final diff review must explicitly verify that pre-existing additive FL paths are not modified by an unrelated change.

A changed existing FL path is therefore a review blocker unless the work item explicitly owns a historical-record correction and documents why mutation, rather than a new additive entry, is required.

## Future prevention rule

Never allocate failure-learning IDs from memory or chat context. Treat the accepted repository directory as the allocator of record: enumerate existing IDs, choose the next free path, and verify the final PR diff preserves all unrelated historical FL blobs.

## Dependency/tooling knowledge change

No dependency or toolchain change is required. Git path identity is insufficient to distinguish an intentional historical edit from an accidental append-only collision; repository-state enumeration and diff review are part of the engineering governance preflight.
