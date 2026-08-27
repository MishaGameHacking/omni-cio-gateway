# FL-046 — Superseded current-status semantics require full consumer migration

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR AMENDMENT 13; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-27**  
WP / PR / reference: **Amendment 13 governance / PR #395 / exact-head Self-Hosted Windows CI run `33051189974`, job `98446832741`**

## Symptom / failing gate

After Amendment 13 guards, formatting, type checks, protected `app:app` checks and read-only release checks passed on exact head `a3ebed8bec66e30ba41282afa0f091a2cf4e6659`, the full Regression Shield reached 2,547 tests and failed only three assertions after **2,544 passed**. Coverage remained above the required threshold at **62.20%**.

The failures were not runtime defects. Two historical WP22A transition test files still required the old current-status phrases `PUBLIC PRODUCTION ACTIVATION LOCKED` or ``PUBLIC_MULTI_USER_ENABLED=false` remains the safe default``. Amendment 13 intentionally supersedes that blanket current-state interpretation with capability-specific `BLOCKED_EXTERNAL` / `LIVE_OPERABLE` semantics while preserving the actual current false runtime flag and external blockers.

## Root-cause analysis

The governance update correctly synchronized the Amendment, machine contract, canonical current status, `AGENTS.md`, `CONTRIBUTING.md`, WP/PR templates and the dedicated public/progressive guards. However, preflight did not search every pre-existing test that consumed `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` by exact historical wording.

Those tests mixed two different responsibilities:

- validating immutable historical WP22A/Amendment-11 evidence, which must remain unchanged;
- validating the **current** V10 authority summary, whose activation semantics were deliberately superseded by Amendment 13.

The historical evidence assertions remained valid. Only the current-status string assertions became stale.

## Blast radius searched

The correction review searched repository consumers for both obsolete current-status markers and distinguished current-state tests from accepted historical evidence. The stale executable assertions were confined to:

- `tests/test_v10_wp22a_phase5_transition.py`;
- `tests/test_wp22a_phase4_free_preview_authorization.py`.

Historical Amendment-10/11/12 documents, Phase-4/5 contracts and authorization records containing older activation language are retained as historical accepted evidence and are not rewritten as if Amendment 13 had always existed.

The already-updated `tests/test_v10_public_free_multi_user_plan.py` uses the Amendment-13 progressive semantics and therefore did not require correction.

## Why preflight missed it

Focused Amendment-13 checks validated the new authority surfaces and new regression tests, but the analogous-pattern search concentrated on live documentation/guards rather than all legacy tests that parse the canonical status file. The full protected Regression Shield was the first gate broad enough to execute these older transition consumers together with the new status semantics.

## Corrective change

The stale transition tests now preserve the facts that still matter while consuming the new current authority correctly:

- `PUBLIC_MULTI_USER_ENABLED=false` remains asserted as the current runtime fact;
- `Amendment 13 — progressive capability activation` is required;
- `current runtime state, not a V10-wide release lock` is required;
- current user-facing activation remains represented as `BLOCKED_EXTERNAL` where real gates remain;
- WP23 remains locked and `PRODUCT IMPLEMENTATION PAUSED` / `START V10 WEB VISUAL SYSTEM UPDATE` remain unchanged.

The progressive capability guard now reads the affected current-status consumer tests before expensive full-suite execution, requires the Amendment-13 markers and rejects reintroduction of the two obsolete blanket-lock assertions.

## Permanent regression / guard

`python scripts/check_v10_progressive_capability_activation.py` now fails early when the reviewed current-status consumer tests:

- stop recognizing Amendment 13 progressive capability semantics;
- stop recognizing `BLOCKED_EXTERNAL` / current-runtime-not-release-lock semantics; or
- reintroduce the exact obsolete current-status assertions that caused this Regression Shield RED.

The full Regression Shield remains authoritative and is not narrowed or weakened.

## Future prevention rule

When a governance amendment intentionally supersedes current-status semantics:

1. search all tests/scripts that consume the canonical current-status file or the superseded marker before the first expensive CI cycle;
2. update **current-state consumers** in the same coherent change;
3. preserve historical accepted documents/contracts as historical evidence unless the amendment explicitly requires a lifecycle note rather than rewriting their original meaning;
4. keep underlying fail-closed facts such as false runtime flags and unpassed external gates explicit even when the higher-level activation model changes;
5. add an early deterministic guard for the superseded consumer class when the lesson is reusable.

## Dependency/tooling knowledge change

No dependency or toolchain change is required. The lesson is about semantic authority migration across repository consumers: focused governance guards and the full Regression Shield protect different layers and both remain mandatory.
