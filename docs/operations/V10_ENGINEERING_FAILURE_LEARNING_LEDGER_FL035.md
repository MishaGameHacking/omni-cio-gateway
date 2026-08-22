# FL-035 — Provider terminal failure must retain a safe root-cause class

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 4; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-22**  
WP / reference: **WP22A Phase 4 Render + Neon synthetic preview / deployment run `32578633564` on accepted main `38f79cd5425bda1e745bb61a3eb560671db4ee8e`**

## Symptom / failing gate

The accepted-main deployment proved the complete protected pre-provider chain and Neon bootstrap:

- exact-main Regression Shield re-verification passed for `38f79cd5425bda1e745bb61a3eb560671db4ee8e`;
- all focused Phase 4 deployment-source tests passed;
- the zero-charge Render attestation and Neon Free-plan boundary passed;
- the Frankfurt Neon project was reused;
- migrations, existing-role convergence, runtime grants and synthetic seed completed;
- the separate Free Render service `omni-cio-v10-web` was created.

The first Render deploy then terminated and the provisioner emitted only:

`PHASE4_FREE_PREVIEW=STOPPED code=RENDER_DEPLOY_FAILED`

Render independently reported that the exact-main deploy failed, but the accepted workflow did not retain whether the provider terminal state was `build_failed`, `update_failed`, `pre_deploy_failed`, `canceled` or another allowlisted Render terminal state.

## Root cause

This entry records the **diagnostic/control-plane root cause**, not the still-unproven application failure inside Render.

`_wait_render_deploy()` correctly failed closed on every terminal Render failure, but intentionally collapsed all terminal statuses into one generic `RENDER_DEPLOY_FAILED` classification. That was sufficient to stop unsafe acceptance, but insufficient to distinguish build failure from start/update/health failure after a real provider attempt.

Because provider credentials are correctly unavailable to pull-request jobs and raw Render logs may contain untrusted/free-form content, ordinary PR CI could not recover that missing classification after the fact. The accepted-main workflow therefore lost the minimum safe provider evidence needed for the next root-cause step.

## Blast radius searched

The review covered:

- exact accepted-main deployment run `32578633564` and its step outcomes;
- Render's independent failure notification for the exact accepted commit;
- `scripts/provision_v10_render_neon_preview.py` terminal deploy-status handling;
- `.github/workflows/v10-phase4-free-preview-deploy.yml` secret scoping and failure path;
- `apps/api/hosted_preview.py` startup/health requirements;
- existing Windows frontend/type/lint/test/build routing;
- the absence of a provider-secret-bearing PR diagnostic path by design;
- Render's current public API schemas for deploy statuses and service events;
- Render Hobby pipeline-minute accounting and the documented `pipeline_minutes_exhausted` lifecycle event that can prevent a build when no paid continuation is available;
- same-SHA retry ambiguity and the risk of attaching an earlier failed deploy to a later failure that occurred before Render;
- adjacent risks from printing raw provider event/log text.

The fix does not widen Render/Neon authority, create another provider workflow, modify the protected V9 service, expose a provider secret, enable public registration, enable broker write or unlock WP23.

## Why preflight missed it

Preflight verified that provider failures remained RED and secret-safe, but it tested the generic fail-closed behavior rather than the **diagnostic resolution** required after a real terminal failure. The first real Render deploy was therefore able to prove that the stop path worked while simultaneously proving that the stop path did not retain enough safe evidence for root-cause isolation.

The previous Phase 4 corrections concentrated on provider URL authority and PostgreSQL 18 create/retry semantics. They did not yet exercise a real Render terminal failure after successful Neon convergence.

A second adjacent gap was found during full-diff review before another accepted-main retry: exact SHA alone is not a sufficient causal key when the same accepted SHA can be retried. Without an attempt boundary, a later non-Render failure could accidentally inherit an earlier Render failure classification from the same SHA.

A third gap was found from the current provider contract: Render exposes `pipeline_minutes_exhausted` separately from ordinary build/deploy failure. On a Hobby workspace, included Starter pipeline minutes are finite; if they are exhausted and no payment method or permitted spend exists, Render can stop new builds before an ordinary failed terminal deploy transition. Collapsing that capacity condition into `BUILD_FAILED` or waiting only for a deploy terminal state would incorrectly send engineering toward application source changes or a misleading timeout.

## Corrective change

Add one read-only, accepted-main-only diagnostic companion to the existing canonical workflow:

- discover exactly one `omni-cio-v10-web` service through the authenticated Render API;
- capture a UTC lower-bound timestamp immediately before the canonical provisioner starts;
- require exactly one Render deploy bound to the exact accepted-main SHA and created at or after that current-attempt boundary;
- reject stale prior deploys and multiple current-attempt matches instead of selecting one heuristically;
- accept only Render's documented deploy-status enum;
- query only the documented `pipeline_minutes_exhausted` service-event type from the same current-attempt boundary and classify it as `PIPELINE_MINUTES_EXHAUSTED` only when exactly one current event exists, including when the current deploy remains `created` or `queued` because its build was prevented from starting;
- when no current pipeline-exhaustion event exists, require the selected deploy itself to be an allowlisted failed terminal state before ordinary deploy-failure diagnosis;
- inspect only the matching structured `deploy_ended` event for ordinary deploy failure;
- if that event links a failed build by provider build ID, inspect only one matching structured `build_ended` event;
- reduce structured reason fields to an allowlisted classification such as `PIPELINE_MINUTES_EXHAUSTED`, `BUILD_FAILED`, `NON_ZERO_EXIT`, `EARLY_EXIT`, `OOM_KILLED`, `TIMED_OUT`, `UNHEALTHY` or `EVICTED`;
- never print provider free-form reason text, raw logs, URIs, credentials or headers;
- run this diagnostic only after the canonical provisioner has already failed, and always preserve the original non-zero deployment result.

The diagnostic is not a bypass and cannot turn a failed apply GREEN. If correlation is stale, ambiguous, malformed or unsupported, the diagnostic reports unavailable and the original provider failure remains authoritative.

## Permanent regression / guard

Deterministic tests cover:

- exact-release deploy binding;
- UTC current-attempt lower-bound validation;
- rejection of a failed deploy from an earlier retry of the same SHA;
- rejection of multiple current-attempt deploy matches;
- rejection of live/non-failed deploys when no unique capacity event explains them;
- current-attempt `pipeline_minutes_exhausted` classification;
- capacity classification of a current queued deploy whose build was prevented from starting;
- stale pipeline-exhaustion event rejection/fallback;
- ambiguous multiple current pipeline-exhaustion events;
- wrapper/list response handling;
- allowlisted terminal-status validation;
- linked deploy-to-build event binding;
- structured reason classification;
- rejection of unknown provider statuses;
- omission of arbitrary provider text from workflow output;
- workflow producer/consumer wiring that captures the attempt boundary before provisioning and passes it to the diagnostic.

The canonical Phase 4 workflow compiles and runs these tests before any provider mutation, then invokes the diagnostic only inside the same accepted-main secret scope if provisioning fails.

## Future prevention rule

For external provider mutations, fail-closed status is necessary but not sufficient. Every finite provider wait loop must preserve a minimal, allowlisted, non-secret terminal classification that distinguishes build/config/start/health/capacity classes without copying arbitrary provider output into CI.

Diagnostic correlation must bind not only to release identity but also to the current mutation attempt when retries of one release are possible. If exact causal correlation cannot be proven, return unavailable rather than selecting a recent-looking provider event.

Provider billing/quota/capacity events are not application defects. Under a zero-charge boundary, they must remain distinct and must never trigger an automatic paid plan, payment-method addition or spend-limit increase.

Provider diagnostic authority must stay in the same or narrower accepted-main secret boundary as the mutation itself. Do not create temporary secret-bearing workflows or expose provider credentials to PR code.

## Dependency/tooling knowledge change

Render's current public API exposes a finite deploy-status enum including `build_failed`, `update_failed`, `pre_deploy_failed`, `canceled` and `deactivated`, plus structured service events such as `deploy_ended`, `build_ended` and `pipeline_minutes_exhausted`. Hobby currently includes a finite Starter pipeline-minute allowance; when that allowance is exhausted and no paid continuation is permitted, new builds can be stopped before a normal failed deploy transition. Those structured fields are a safer engineering evidence surface than copying raw dashboard logs into GitHub Actions output, but they still require causal binding to the current provision attempt before being treated as root-cause evidence.
