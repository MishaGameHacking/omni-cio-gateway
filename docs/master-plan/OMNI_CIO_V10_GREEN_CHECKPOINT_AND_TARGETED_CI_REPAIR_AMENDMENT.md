# Omni-CIO V10 — Green Checkpoint & Targeted CI Repair Law / Amendment 16

**Status:** OWNER-APPROVED / EFFECTIVE ONLY WHEN ACCEPTED ON PROTECTED `main`  
**OWNER decision:** 2026-09-08  
**Scope:** all current and future repository development, maintenance, recovery, governance, CI and review work  
**Product progress effect:** NONE by itself  
**Runtime authority effect:** NONE by itself

## 1. Purpose

This amendment replaces the old assumption that CI must be conserved as an expensive late-stage verifier. Omni-CIO now treats fast CI, Sonar and independent review as continuous checkpoint certification.

The primary engineering objective is:

> **Never continue functional development on top of a known or uncertified RED checkpoint.**

Every logical checkpoint must become fully certified GREEN before the next functional checkpoint begins. When a check fails, the branch immediately enters `REPAIR_ONLY`; the defect is diagnosed and corrected before feature work continues.

This amendment does not promise defect-free software. It establishes the strongest practical process for preventing known defects and bad patterns from propagating into later code.

## 2. Precedence and supersession

The V10 Master Plan, Program Lock, security boundaries, exact-head merge policy and protected V9 baseline remain active.

Where verification timing or publication discipline conflicts, Amendment 16 explicitly supersedes:

- Amendment 12 Section 5 `Single Remote Publication Default` as a mandatory default;
- Amendment 12 Section 7 `HEAD FREEZE and verification-batch observation law` to the extent that it requires waiting for the whole safe batch before beginning ordinary repair;
- Amendment 12 Section 8 `batch-correction law` to the extent that it forbids immediate checkpoint repair or requires all independent failures to be collected before repair starts;
- Amendment 12 Section 9 only to the extent that it assumes one final published implementation head is the normal verification unit;
- Amendment 8 / Engineering Quality wording that treats full CI as something to defer primarily because it is expensive;
- live guidance/templates that require `INTEGRATION_READY` before any useful published checkpoint verification;
- the mandatory duplicate DRAFT→READY full verification cycle when the exact PR head SHA has not changed and no applicable check is semantically dependent on the PR-state transition.

Amendment 12 remains active for execution-unit grouping, ordered internal milestones, mandatory split triggers, branch ledger/dashboard, accepted-main progress semantics and major System Update sequencing.

Amendment 8 remains active for root-cause analysis, blast radius, regression guards, exact-head SUCCESS-only merge, full-diff/review requirements, security/recovery discipline and post-merge verification.

Historical accepted documents are not rewritten to pretend the old rule never existed. Later Amendment 16 controls the conflicting current behavior.

## 3. Core law — Green Checkpoint

A **checkpoint** is the current published logical branch head whose correctness must be established before more functional scope is added.

For every implementation, defect, maintenance, governance or recovery branch:

`WRITE -> FOCUSED PREFLIGHT -> CHECKPOINT SHA -> CI + SONAR + REVIEW -> CERTIFIED_GREEN -> NEXT CHECKPOINT`

If any applicable check or material review finding becomes RED:

`CHECKPOINT_RED -> REPAIR_ONLY -> ROOT CAUSE -> TARGETED PROOF -> REPLACEMENT SHA IF CODE CHANGED -> FULL CERTIFICATION -> CERTIFIED_GREEN`

Rules:

1. The next functional checkpoint MUST NOT be created while the current checkpoint is `PENDING`, `RED`, `REPAIR_ONLY` or otherwise uncertified.
2. A known defect MUST NOT be carried forward with “fix later” intent.
3. A pattern first introduced by an uncertified checkpoint MUST NOT be copied into additional code.
4. Repair work is allowed immediately; unrelated feature progress is not.
5. Documentation-only, governance and test changes are checkpoints when they are published and can affect repository authority or CI behavior.

## 4. Checkpoint states

The canonical states are:

- `PENDING` — published checkpoint is being verified;
- `RED_REPAIR_ONLY` — at least one applicable failure/material finding exists; only diagnosis/repair work may advance;
- `TARGET_REPAIRED` — the proved failing surface passes its targeted recheck on the corrected working state/replacement SHA;
- `CERTIFIED_GREEN` — the current exact SHA has all applicable required verification and review satisfied;
- `MAIN_RED_STOP` — protected `main` has an applicable post-merge RED; ordinary feature progress is blocked until an accepted repair restores GREEN.

Only `CERTIFIED_GREEN` permits the next functional checkpoint.

## 5. Before creating/publishing a checkpoint

The developer/agent performs the applicable focused preflight first:

- format/lint/type/compile checks for affected languages;
- focused positive and negative tests;
- directly affected build/browser/schema/config validation;
- root-cause/blast-radius analysis for a known defect;
- analogous-pattern and producer/consumer inspection where material;
- deterministic regression guard for a reusable defect class;
- secret/private-data review;
- full changed-surface review appropriate to the checkpoint.

Preflight exists to keep obvious defects out of CI. It is not a reason to avoid CI after the checkpoint is ready.

CI duration/cost is not a reason to skip required checkpoint certification. If CI capacity later becomes constrained, routing/parallelism/caching must be improved without weakening the Green Checkpoint law.

## 6. Immediate RED response — do not wait to start repair

The first material RED immediately changes branch mode to `RED_REPAIR_ONLY`.

The developer/agent MUST begin diagnosis as soon as useful failure evidence exists. It is **not required to wait for every independent job to finish before starting ordinary diagnosis and repair**.

Other independent checks may continue in parallel. Any additional findings that arrive before the corrected checkpoint is finalized must be reviewed and, where relevant, incorporated into the same repair reasoning.

The repair process remains systemic:

1. identify the actual root cause;
2. determine blast radius;
3. search analogous repository patterns;
4. inspect directly coupled producers/consumers/config/workflows;
5. inspect reasonable adjacent failure modes;
6. fix the defect class rather than only the first failing line;
7. add or strengthen deterministic regression coverage;
8. run the smallest canonical targeted check that proves the reported failure is fixed.

Do not suppress, ignore, weaken, skip or reclassify a real defect merely to obtain GREEN.

## 7. Same-SHA targeted rerun — only when source is unchanged

GitHub Actions can re-run one specific job or only failed jobs from an existing run. GitHub re-runs use the same original `GITHUB_SHA` and `GITHUB_REF`.

Therefore a same-SHA rerun is valid only when the repository source/config under test has not changed.

Use same-SHA targeted rerun for evidence such as:

- a proved transient runner/network/package-registry failure;
- an external service transient that did not require repository change;
- a cancelled job whose code/config remains unchanged;
- another infrastructure failure where the correct repair is outside repository source and the exact SHA remains valid.

Preferred action: re-run only the failed job. Re-run all failed jobs only when multiple independent jobs share the same unchanged-code failure class.

A transient classification must be evidence-based. Repeated identical failure is not endlessly rerun until lucky GREEN; it becomes an infrastructure/workflow defect and the branch remains RED.

## 8. Code/config repair requires a replacement SHA

Git commits are immutable objects. `git commit --amend` replaces the branch tip by **creating a new commit**, so changed content necessarily has a new SHA.

If source/config/test/governance content changes to fix the RED:

1. prior CI/Sonar/review results belong to the old SHA and are not final evidence for the repaired code;
2. run the targeted affected check locally or through an exact-SHA targeted verifier as soon as possible;
3. update the same **logical checkpoint** by amend/history replacement when safe and branch policy permits;
4. if history rewrite is unsafe/unavailable, a repair commit is allowed, but it is explicitly part of the same `RED_REPAIR_ONLY` checkpoint and does **not** authorize new feature scope;
5. publish the replacement SHA;
6. obtain full checkpoint certification on that replacement SHA before creating the next functional checkpoint.

Never force-update protected `main`. Never rewrite another contributor's shared history merely to preserve a one-commit appearance.

The rule is semantic, not cosmetic:

`A1 RED -> A2 repaired replacement -> A2 CERTIFIED_GREEN -> B allowed`

is valid.

`A1 RED -> B feature work -> C feature work -> later fix A`

is forbidden.

## 9. Targeted proof versus full certification

A targeted recheck answers one question: **is the reported defect fixed?**

Full certification answers the different question: **is the complete current exact checkpoint safe to build upon?**

Therefore after a code-changing repair:

1. targeted proof SHOULD run first or as early as possible;
2. once targeted proof passes and the replacement SHA is final, all applicable checkpoint checks must certify that exact SHA;
3. old GREEN results from the superseded SHA do not count as final certification for the replacement SHA;
4. only then may the next functional checkpoint begin.

This is intentionally stricter than treating a single fixed job as proof that unrelated surfaces were not regressed by the correction.

## 10. Sonar / independent code-review law

Sonar and independent review are active programming assistants, not merge-time decoration.

For every checkpoint that changes code:

- Sonar Quality Gate must pass when applicable;
- `new issues = 0` is the default checkpoint requirement;
- unresolved new Security Hotspots = 0;
- unresolved material Reliability/Security/Maintainability findings in changed/touched code = 0;
- Gitar/SAST/check annotations and other applicable independent review findings must be inspected and material findings corrected;
- bot approval never replaces engineering judgment.

Historical unrelated debt is not silently reclassified as new checkpoint debt. However a touched/propagated defect, or the same defect class found in the reasonable blast radius, must be addressed before certification or explicitly proven unrelated/non-material according to the owning review policy.

## 11. Exact GREEN definition

`CERTIFIED_GREEN` requires the **current exact checkpoint SHA** to satisfy all applicable requirements:

- applicable CI checks actually executed and concluded `success`;
- Sonar Quality Gate passed when applicable;
- no unresolved new Sonar issues/hotspots in checkpoint scope;
- applicable independent review/SAST/Gitar findings dispositioned with zero unresolved blocking material finding;
- complete changed-surface review performed;
- unresolved blocking review threads = 0;
- no known P0/P1 correctness/security/recovery blocker.

For an applicable gate, `failure`, `cancelled`, `queued`, `pending`, `in_progress`, `timed_out`, `action_required`, `stale`, `neutral` and `skipped` are not GREEN.

## 12. PR lifecycle without redundant same-SHA certification

The final merge head must be `CERTIFIED_GREEN`.

Changing a PR from DRAFT to READY does **not by itself** invalidate exact-SHA certification if:

- the head SHA is unchanged;
- all applicable required checks for that exact SHA have already succeeded;
- no check is semantically dependent on the DRAFT/READY transition;
- GitHub rulesets/branch protection do not require a fresh state-triggered run;
- review requirements are satisfied on the same head.

If an applicable workflow is intentionally state-dependent and triggers on `ready_for_review`, its success is still required.

Any source/config/test/document commit that changes the head creates new evidence requirements for that new exact SHA.

Normal landing remains:

`current exact head CERTIFIED_GREEN -> full Files changed/review -> zero blockers -> squash merge -> exact-new-main post-merge verification`.

## 13. Protected `main`

Protected `main` is never amended or force-rewritten.

If an applicable post-merge check on current `main` is RED:

1. state becomes `MAIN_RED_STOP`;
2. ordinary feature/milestone progress pauses;
3. create/use a focused repair branch from current accepted main;
4. apply this same checkpoint law to the repair branch;
5. merge only after exact-head certification and normal review;
6. verify the resulting new `main` with Regression Shield/owning post-merge gates.

A known RED `main` must not become the silent base for unrelated feature expansion.

## 14. Safety-abort exception

Immediate repair never means continuing a dangerous run.

Stop/contain immediately if continued execution can expose secrets/private data, reach broker/Real-money authority, perform destructive migration/provider mutation, create uncontrolled paid spend or cause cross-tenant/privacy harm.

Money/security authority remains fail-closed.

## 15. Integrated System Update interaction

Amendment 16 changes checkpoint verification cadence, not integrated scope/order.

For an `INTEGRATED_SYSTEM_UPDATE`:

- member milestones remain ordered;
- each meaningful published implementation checkpoint must become `CERTIFIED_GREEN` before the next functional checkpoint/milestone work builds on it;
- `INTEGRATION_READY` remains the final whole-update readiness state before final landing review, not a prohibition on earlier checkpoint certification;
- Execution Ledger/dashboard remain required;
- mandatory split triggers remain active;
- accepted program progress still changes only after final squash merge + exact-main post-merge acceptance.

## 16. Existing/in-flight branch transition

When Amendment 16 becomes accepted on `main`:

- already merged historical commits are not rewritten;
- already running PRs keep their existing historical evidence but must adopt `RED_REPAIR_ONLY` / Green Checkpoint behavior for any subsequent head;
- an existing RED branch may not add unrelated feature scope before its current defect is repaired and the replacement head is certified;
- existing branch history need not be cosmetically rewritten solely to imitate the new checkpoint structure.

## 17. Protected invariants — unchanged

This amendment does not alter:

- protected V9 `app:app` baseline/rollback;
- one canonical product/repository/Core/Web line;
- current execution-unit authority or member milestone order;
- tenant isolation / PostgreSQL RLS/FORCE-RLS;
- secret/private-data exclusion from GitHub/chat/CI/artifacts;
- `PUBLIC_MULTI_USER_ENABLED=false` until its owning gate;
- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no transfer/withdrawal/margin/leverage/uncovered-short authority;
- Real-money approval boundaries;
- squash-only protected-main integration;
- exact-main post-merge Regression Shield/owning gates.

A merge, checkpoint GREEN, CI success, Sonar pass, Cloudflare deployment, AI output or OWNER START command is never broker-submit authorization.

## 18. Operational summary

The rule future agents/developers must remember is:

```text
1. WRITE one logical checkpoint.
2. Run affected focused preflight.
3. Publish checkpoint -> CI + Sonar + review.
4. Any RED -> immediately REPAIR_ONLY; no next feature checkpoint.
5. Start root-cause repair immediately; do not wait for every other job just to begin.
6. Source unchanged -> rerun only the failed job on the same SHA when transient classification is proved.
7. Source changed -> targeted proof -> replacement SHA -> old final evidence stale.
8. Fully certify the replacement exact SHA.
9. Require CI SUCCESS + clean Sonar/new-code review + zero blocking findings.
10. Only CERTIFIED_GREEN permits the next functional checkpoint.
11. After squash merge, exact new main is verified separately.
```

## 19. Governance acceptance gate

Amendment 16 becomes active only after the focused governance PR containing this law, its machine contract, live-guidance synchronization and deterministic guard/tests:

- passes applicable exact-head checks with `success`;
- passes independent review with zero unresolved blocking threads;
- is squash-merged through protected `main`;
- completes required exact-new-main Regression Shield/governance post-merge checks successfully.

Until then, this OWNER-approved file is proposal content on an unaccepted branch and does not override accepted `main`.

## 20. External behavior facts used by this law

- GitHub Actions official documentation: a re-run can target a specific job or failed jobs and uses the same original `GITHUB_SHA` / `GITHUB_REF`: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs
- GitHub Actions manual dispatch can target a branch/ref and accept inputs when `workflow_dispatch` is defined: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
- Git official documentation: `git commit --amend` replaces the branch tip by creating a new commit: https://git-scm.com/docs/git-commit
- Sonar Clean-as-You-Code/new-code quality model: https://docs.sonarsource.com/sonarqube-cloud/standards/about-new-code
