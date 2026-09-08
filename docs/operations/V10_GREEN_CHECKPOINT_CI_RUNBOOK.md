# V10 Green Checkpoint CI Runbook

Canonical law: `docs/master-plan/OMNI_CIO_V10_GREEN_CHECKPOINT_AND_TARGETED_CI_REPAIR_AMENDMENT.md`.

## Core loop

```text
ONE CHECKPOINT
-> focused preflight
-> publish exact SHA
-> CI + Sonar + independent review
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

Always inspect root cause, blast radius, analogous patterns, directly coupled producers/consumers/config/workflows, adjacent failure modes and regression coverage.

## 3. Same source, same SHA

If no repository source/config changes are required and the failure is proved transient/infrastructure-only, re-run only the specific failed GitHub Actions job on the same SHA. Do not re-run everything by default.

A repeated identical failure must be treated as an infrastructure/workflow defect rather than retried until lucky GREEN.

## 4. Source changed

Changed content requires a replacement SHA. Prefer amending the current logical checkpoint when safe. If history rewrite is unsafe/unavailable, use a repair commit but remain in `RED_REPAIR_ONLY`; no new feature scope is allowed.

First prove the reported defect with the smallest canonical targeted check. Then run full applicable certification on the final replacement SHA.

## 5. Sonar and review

For changed code, checkpoint certification requires applicable Sonar Quality Gate PASS, zero new issues by default, zero unresolved new Security Hotspots and zero unresolved material Reliability/Security/Maintainability findings. Inspect Gitar/SAST/check annotations and review threads as well.

## 6. Green definition

Only `success` counts as GREEN for an applicable CI gate. `failure`, `cancelled`, `queued`, `pending`, `in_progress`, `timed_out`, `action_required`, `stale`, `neutral` and `skipped` do not.

Only `CERTIFIED_GREEN` permits the next functional checkpoint.

## 7. Main

If post-merge `main` becomes RED, use `MAIN_RED_STOP`. Pause unrelated feature development and repair through a focused branch. Never amend or force-rewrite protected `main`.

## 8. Safety exception

Stop dangerous execution immediately for secret/private-data exposure, broker/Real-money reachability, destructive migration/provider mutation, uncontrolled spend or cross-tenant/privacy risk.
