# Omni-CIO V10 — CI Cost Control / Zero-Budget Hosted Runner Standard

Status: **OWNER-APPROVED POLICY / EFFECTIVE ONLY AFTER GOVERNANCE MERGE TO `main`**  
Date: 2026-08-16  
Scope: GitHub Actions budgets, hosted-runner use, CI routing, paid CI prerequisites and OWNER billing handoffs.

## 1. Purpose

This standard separates three different facts that must never be conflated:

1. whether the source code is correct;
2. whether a GitHub Actions workflow is applicable and correctly routed;
3. whether the external GitHub billing/budget state currently permits a GitHub-hosted job to start.

A billing/budget block is not a code defect, but a RED applicable check still blocks merge under the V10 GREEN-merge policy.

## 2. Confirmed external-state observation — 2026-08-16

The OWNER supplied a browser screenshot of the personal GitHub account `MishaGameHacking` → **Billing & licensing → Budgets and alerts**.

The screenshot shows the account-level GitHub Actions budget at **USD 0** with **Stop usage = Yes**. Other shown metered-product budgets are also zero with stop-usage enabled.

This observation explains the GitHub-hosted Actions annotation seen on current V10 PR runs: the jobs do not start and GitHub reports a payment/spending-limit blocker.

This is a time-bounded external-state observation, **not an immutable architecture constant**. Future engineering must re-verify current GitHub billing/budget state before assuming it is unchanged.

No card data, billing identifiers or private payment details are recorded in GitHub.

## 3. Zero-budget law

When an OWNER-controlled budget is zero or a hard stop is enabled:

- do not silently increase the budget;
- do not disable `Stop usage when budget limit is reached`;
- do not add/replace a payment method;
- do not ask the OWNER to authorize spend merely to avoid doing engineering work;
- do not classify the resulting hosted-runner startup failure as a code failure;
- do not merge around the RED check;
- do not repeatedly trigger a hosted workflow that is already known to be unable to start.

Any budget/payment mutation requires a separate explicit OWNER decision after engineering states the exact reason, expected cost exposure, alternative zero-cost path and rollback.

## 4. Preferred engineering response

Before requesting paid hosted execution, engineering must first determine whether the owning verification semantics can be preserved with already-paid or zero-cost capacity:

1. repository-local deterministic preflight;
2. Lenovo self-hosted authoritative Windows runner;
3. source-controlled equivalent validation on another already-authorized zero-cost/self-hosted runner;
4. only then, if a required clean-room/hosted semantic cannot be reproduced safely, request an explicit OWNER decision about paid GitHub-hosted execution.

The cost-control rule must not be used to weaken validation. Moving a job from GitHub-hosted to Lenovo is acceptable only when the required semantic is preserved or the owning contract explicitly permits the replacement.

A disposable hosted clean-room requirement may not be silently deleted merely because hosted usage is blocked.

## 5. GREEN-status interaction

The V10 GREEN-merge law remains unchanged:

- every **applicable** exact-head check must conclude `success`;
- a budget-blocked applicable hosted check remains RED and blocks merge;
- if a hosted workflow is genuinely non-applicable under the accepted CI routing contract, fix its trigger/routing so it does not appear as a misleading failed/skipped PR check;
- if it remains required, restore an accepted execution path rather than bypassing it.

Classification answers **why** a check failed; classification never grants merge authority.

### 5.1 Capacity-deferred compatibility mode

While the source-controlled capacity state is `BLOCKED_OWNER_ZERO_BUDGET_HARD_STOP`, GitHub-hosted compatibility is treated as an **acceleration/clean-room evidence lane that is unavailable**, not as the authoritative merge gate.

The workflow must still execute a real check on the Lenovo runner and must report one of two truthful outcomes:

- `NOT_APPLICABLE` — the source-controlled path router says that compatibility family is not required for the changed surface; or
- `REQUIRED_BY_PATH_BUT_CAPACITY_BLOCKED` — the path normally merits disposable hosted compatibility, but current OWNER-controlled capacity prevents that hosted run.

The successful routing/capacity job means only that the routing policy was evaluated correctly. It **must not claim** that Python 3.14.6 or hosted Node clean-room compatibility passed when the hosted VM did not run.

A job-level GitHub `skipped` result is not accepted as V10 GREEN evidence under this policy. Non-applicable/capacity-deferred lanes therefore execute a small deterministic routing/capacity job and finish successfully instead of being represented as skipped.

This mode does not remove the required `V10 authoritative merge gate` on Lenovo. It also does not authorize a STABLE release to fabricate clean-room evidence: release provenance that requires hosted compatibility remains blocked until actual compatible evidence exists or a later OWNER-approved equivalent clean-room mechanism is accepted.

### 5.2 Live V9 authority evidence while capacity is blocked

The protected V9 deployed-authority probe is different from deterministic CI. It is intended to observe the public deployed Render endpoint from an independent network path, not merely to validate source code.

During governance PR #322, a bounded self-hosted diagnostic established that the Lenovo route is **not** semantically equivalent for this purpose: DNS resolution succeeded, but TCP/443 to the protected Render endpoint timed out and HTTP failed at connect time. Extending retries cannot turn that network path into independent deployed evidence.

Therefore the current machine state is:

`DEFERRED_NO_TRUSTED_ZERO_COST_ROUTE_NOT_PASS`

This means:

- actual deployed V9 authority evidence is **not PASS** and must never be presented as PASS;
- automatic daily/PR live execution is suspended while the trusted hosted route is budget-blocked and the Personal Node route is non-equivalent;
- the real `Live Gateway Authority Acceptance` workflow remains source-controlled as a manual GitHub-hosted probe with the original public `/health` + `/openapi.json` semantics;
- PRs that change the live-evidence boundary run the separate `V10 Live Gateway Authority Contract` on Lenovo, which verifies routing, safety and non-fabrication but explicitly does **not** claim deployed live evidence;
- a governance-only PR that does not alter the deployed V9 runtime, deployment or Action authority may merge when all of its applicable exact-head code/governance checks are GREEN even though the unrelated live evidence is deferred;
- any V9 runtime/deployment/Action-authority release that requires production acceptance remains blocked until real manual hosted acceptance succeeds on the exact accepted source/deployment state;
- restoring automatic live probing requires re-verifying a trusted independent network route and current OWNER-controlled hosted capacity, then landing the routing restoration through its own GREEN PR.

This is degradation by truthful evidence classification, not a bypass. The protected V9 source/rollback remains preserved while deployed-live freshness is explicitly unknown/deferred.

## 6. CI design consequence

Future V10 WPs must not make correctness depend unnecessarily on metered hosted capacity when the accepted Lenovo/self-hosted architecture can provide equivalent deterministic evidence.

Hosted capacity remains useful for fast feedback and disposable compatibility where the accepted contract requires it, but it is not the sole source of truth. Heavy repeatable validation remains preferentially placed on the Lenovo runner when safe and semantically correct.

During the current zero-budget state:

- fast policy/source checks are allowed to run on Lenovo because their semantics are deterministic and do not require a disposable VM;
- frontend fast validation may run on the already accepted exact Node/npm installation on Lenovo;
- the dedicated hosted toolchain workflow becomes an explicit capacity/applicability contract and does not pretend that a disposable clean-room VM executed;
- the existing release-provenance contract continues to require truthful compatibility evidence for release claims.

Before opening or moving a PR to final review, engineering should inspect whether any known budget-blocked hosted workflow will become an applicable check. Known unavoidable RED must be resolved at routing/capacity/prerequisite level before the final GREEN cycle.

When hosted capacity is restored, engineering must re-verify the external account state and use a focused GREEN governance/CI PR to restore the hosted acceleration lanes. Do not infer recovery merely from the passage of time.

## 7. OWNER handoff rule for paid CI

If paid hosted capacity is genuinely required, the OWNER instruction must follow `V10_OWNER_ACTION_HANDOFF_STANDARD.md` and include:

- the direct official GitHub billing/budget URL;
- the exact product/scope being changed;
- the minimum proposed budget or permission change;
- whether `Stop usage` changes;
- the maximum reasonably expected cost exposure for the requested validation;
- why self-hosted/zero-cost alternatives are insufficient;
- the expected result;
- STOP conditions;
- explicit warning not to change unrelated product budgets.

No billing mutation is implied by `START V10`, a PR, a failed hosted job or an AI recommendation.

## 8. Protected invariants

This standard does not change:

- `app:app` protected V9 compatibility;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no broker-write authority expansion;
- no transfer/withdrawal authority;
- protected V9 rollback;
- Master Plan WP ordering;
- all-applicable-checks GREEN requirement.
