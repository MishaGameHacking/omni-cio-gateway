# V10 Green Checkpoint CI Runbook

Canonical law: `docs/master-plan/OMNI_CIO_V10_GREEN_CHECKPOINT_AND_TARGETED_CI_REPAIR_AMENDMENT.md`.
Machine contract: `docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json`.

## Core loop

```text
ONE CHECKPOINT
-> focused preflight
-> publish exact SHA
-> GitHub-native CI/security + independent review
-> RED = REPAIR ONLY
-> immediate root-cause repair
-> TARGETED RECHECK
-> replacement SHA if source changed
-> FULL CERTIFICATION
-> CERTIFIED_GREEN
-> NEXT CHECKPOINT
```

## 1. Before checkpoint

Run the affected local/focused checks first. Do not knowingly publish syntax/type/test/security failures merely because CI is fast.

## 2. When a check fails

Immediately mark the checkpoint `RED_REPAIR_ONLY` and stop unrelated feature progress. Start diagnosis as soon as the failing evidence is useful; do not wait for every independent job merely to begin repair.

Always inspect root cause, blast radius, analogous patterns, directly coupled producers/consumers/config/workflows, adjacent failure modes and regression coverage. Relevant findings arriving from other independent checks before the corrected checkpoint is finalized must still be inspected.

## 3. Same source, same SHA

If no repository source/config changes are required and the failure is proved transient/infrastructure-only, re-run only the specific failed GitHub Actions job on the same SHA. Do not re-run everything by default.

A repeated identical failure must be treated as an infrastructure/workflow defect rather than retried until lucky GREEN.

## 4. Source changed

Changed content requires a replacement SHA. Prefer amending the current logical checkpoint when safe. If history rewrite is unsafe/unavailable, use a repair commit but remain in `RED_REPAIR_ONLY`; no new feature scope is allowed.

First prove the reported defect with the smallest canonical targeted check. Then run full applicable certification on the final replacement SHA.

## 5. Targeted verifier

Canonical workflow: `.github/workflows/v10-targeted-repair.yml`.

Use it only for the current replacement checkpoint after Amendment 16 is accepted on `main` and the workflow is available on the default branch.

Required dispatch rules:

- dispatch the workflow on the branch/ref whose current head is being proved;
- `expected_sha` must be the exact lowercase 40-character current dispatch-ref head;
- the workflow rejects a different/stale SHA;
- checkout is detached at the exact requested SHA and is rechecked after the targeted lane;
- frontend lanes validate installed Node/npm against `docs/architecture/V10_TOOLCHAIN_BASELINE.json` before `npm ci`;
- frontend dependency install uses `--ignore-scripts --no-audit --no-fund`;
- workspace credentials and generated/untracked state are cleaned after the lane.

Canonical lanes are `ruff`, `format`, `mypy`, `pytest`, `governance`, `repository-guards`, `frontend-type`, `frontend-lint`, `frontend-test`, and `frontend-build`.

A targeted verifier PASS proves only the chosen repair surface. It never replaces full applicable certification of the final replacement SHA.

## 6. Quality, security and review

For current/future V10 work after Amendment 18, checkpoint certification uses GitHub-native lint/type/test/coverage/dependency/SAST/secret/security checks plus independent review. Unresolved material correctness/security/maintainability findings are not GREEN. Inspect check annotations and review threads as well. Historical Sonar evidence may remain in the repository, but external Sonar is not active acceptance authority.

## 7. Green definition

Only `success` counts as GREEN for an applicable Omni-CIO project CI gate. `failure`, `cancelled`, `queued`, `pending`, `in_progress`, `timed_out`, `action_required`, `stale`, `neutral` and `skipped` do not.

Only `CERTIFIED_GREEN` permits the next functional checkpoint.

## 8. PR lifecycle

The final merge head must be `CERTIFIED_GREEN`, with complete Files changed/manual diff review, applicable independent review inspected and unresolved blocking review threads = 0.

Changing DRAFT to READY does not by itself invalidate exact-SHA certification when the head is unchanged and no applicable workflow/ruleset is state-dependent. If an applicable `ready_for_review` or equivalent state-dependent gate runs, it must conclude `success`.

Any content-changing commit invalidates prior final exact-head CI/review evidence.

## 9. Main

If post-merge `main` becomes RED, use `MAIN_RED_STOP`. Pause unrelated feature development and repair through a focused branch. Never amend or force-rewrite protected `main`.

## 10. Safety exception

Stop dangerous execution immediately for secret/private-data exposure, broker/Real-money reachability, destructive migration/provider mutation, uncontrolled spend or cross-tenant/privacy risk.
