# FL-058 — Known adjacent bootstrap debt becomes current when an applicable gate reproduces the transport failure

Status: **ADDITIVE FAILURE-LEARNING ENTRY; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-28**  
WP / PR / reference: **Governance PR #402 / issue #406 / exact failing head `6b65c9c8c57e2803478a3ceddd68e9f783fb1018` / accepted main `698be470048f100546354a3ac78d112e8cec7519`**

## Symptom / failing gates

PR #405 had already repaired the first Schannel bootstrap blocker in a deliberately narrow six-workflow dependency closure and explicitly recorded the remaining single-attempt self-hosted workflows as adjacent debt.

After #405 was accepted and PR #402 was re-anchored, a current applicable gate proved that this debt was no longer merely future work:

- `V10 Live Gateway Authority Contract` #72 failed before project code with `curl 56`, missing `close_notify`, incomplete response bytes, `unexpected disconnect`, `early EOF`, and `invalid index-pack output`;
- its downstream policy/evidence checks were skipped;
- the old cleanup path still attempted `git reset --hard HEAD` after checkout had never produced `HEAD`;
- the resulting run was terminal non-GREEN and therefore blocked PR #402.

Independently, accepted-main `V10 Phase 4 Free Preview Deploy` #29 failed with the same transport chain before provider mutation. All provider/deploy steps were skipped, so no Render or Neon mutation occurred. Its completion automatically queued `V10 Hosted Release Alignment`, proving that alignment is a directly coupled current lifecycle consumer rather than a hypothetical future surface.

## Root cause

The repository had split into two bootstrap reliability tiers after #405:

1. six current authority workflows implemented the accepted bounded repository-transport retry and pre-`HEAD`-safe cleanup contract;
2. other current self-hosted workflows still used one unbounded `git fetch`, and several cleanup blocks still assumed checkout had created `HEAD`.

The first narrow repair was valid for its immediate dependency closure. The defect was allowing that deliberately deferred adjacent debt to remain deferred after new evidence showed it had become directly applicable to the current merge and accepted-main lifecycle.

Hosted Release Alignment also had a second read-only Git fetch after the external runtime probe. That refresh protects PASS publication from a main-advance TOCTOU race. A transient transport failure there must not be ignored, retried by rerunning the whole workflow, or allowed to publish buffered PASS.

## Blast radius / directly coupled surfaces

The current PR #402 applicability graph identified the still-single-attempt PR gates that can directly block its DRAFT/READY acceptance:

- live gateway authority routing contract;
- WP16 through WP22 deterministic Web/product gates;
- WP22A clientless access;
- WP22A Phase 2 product-auth tenant gate.

The accepted-main lifecycle recurrence adds:

- Phase-4 free-preview deployment bootstrap;
- Hosted Release Alignment initial bootstrap;
- Hosted Release Alignment post-probe current-main refresh.

Historical one-shot public-acceptance/technical-closeout workflows and the future #401 verifier-provider/runtime migration are not pulled into this repair without current dependency evidence.

## Why preflight missed it

The accepted #405 guard intentionally enforced bounded retry only across the six-workflow blocker dependency closure. It still kept a broader whole-plane security/exact-SHA inventory, but it did not require every known adjacent workflow to adopt retry immediately because doing so would have expanded that urgent PR into unrelated expensive gates.

That was a valid bounded repair decision at the time. The missing prevention rule was temporal: once a deferred analogous surface becomes applicable and reproduces the same root cause, it must move into the current dependency closure immediately rather than waiting for the later broad migration package.

The accepted-main Phase-4 recurrence also demonstrated that downstream workflow topology matters to blast-radius analysis. Repairing a producer bootstrap without inspecting its automatic `workflow_run` consumer can simply move the same transport blocker one gate later.

## Corrective change

Issue #406 extends the already accepted bootstrap pattern only across the current critical set:

- exactly three bounded fetch attempts;
- Git low-speed abort at 1 KB/s for 60 seconds;
- fresh `.git` state for every initial bootstrap attempt;
- job-scoped read token only, with inherited helpers reset and temporary helper removed after every attempt;
- exact reviewed/main SHA verification remains mandatory;
- retry exhaustion fails closed with an explicit diagnostic;
- always-run cleanup handles missing `HEAD` safely;
- tests, lint, type checks, coverage, security scans and provider/deployment mutations remain outside retry loops.

Hosted Release Alignment performs its post-probe main refresh in a fresh temporary Git repository on every attempt. It publishes the buffered runtime PASS only after the bounded refresh succeeds and proves current `main` still equals the expected SHA.

## Permanent guard

`tests/test_v10_ci_action_download_resilience.py` now keeps three separate contracts:

1. whole current self-hosted authority-plane exact-SHA/read-only/headless bootstrap semantics;
2. historical #404 six-workflow retry closure;
3. current #406 critical retry closure, including Phase-4 and Hosted Alignment.

A dedicated Hosted Alignment assertion additionally requires an isolated three-attempt post-probe refresh, helper cleanup, low-speed abort, fail-closed exhaustion, and main-identity comparison before `hosted_alignment_pass.txt` can be published.

## Future prevention rule

A focused dependency closure may intentionally defer analogous debt, but that deferral is conditional, not permanent.

When a deferred analogous surface later becomes applicable to the current PR/lifecycle and reproduces the same root cause:

1. freeze the blocked work;
2. classify the repeated failure from exact logs;
3. recompute the current dependency graph, including automatic downstream workflow consumers;
4. expand only to the newly material dependency closure;
5. add a deterministic guard that distinguishes the current closure from still-future migration scope;
6. accept the infrastructure repair before re-anchoring the blocked product/governance PR.

Do not wait for every analogous workflow to fail independently. Do not use a broad future architecture initiative as an excuse to leave a proven current merge gate unreliable. Conversely, do not bulk-rewrite historical evidence workflows that are not on the current dependency path.

## Dependency/tooling knowledge change

Git for Windows / Schannel transient pack-transfer failure is now known to affect both PR verification and accepted-main deployment/runtime-alignment lifecycle jobs on the persistent self-hosted runner. Bootstrap resilience therefore must be reviewed as a dependency graph property, not only as a property of the first workflow that happened to fail.
