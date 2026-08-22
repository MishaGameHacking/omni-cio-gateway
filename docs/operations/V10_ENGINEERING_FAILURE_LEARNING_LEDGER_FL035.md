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
- adjacent risks from printing raw provider event/log text.

The fix does not widen Render/Neon authority, create another provider workflow, modify the protected V9 service, expose a provider secret, enable public registration, enable broker write or unlock WP23.

## Why preflight missed it

Preflight verified that provider failures remained RED and secret-safe, but it tested the generic fail-closed behavior rather than the **diagnostic resolution** required after a real terminal failure. The first real Render deploy was therefore able to prove that the stop path worked while simultaneously proving that the stop path did not retain enough safe evidence for root-cause isolation.

The previous Phase 4 corrections concentrated on provider URL authority and PostgreSQL 18 create/retry semantics. They did not yet exercise a real Render terminal failure after successful Neon convergence.

## Corrective change

Add one read-only, accepted-main-only diagnostic companion to the existing canonical workflow:

- discover exactly one `omni-cio-v10-web` service through the authenticated Render API;
- find the most recent deploy bound to the exact accepted-main SHA;
- accept only Render's documented deploy-status enum;
- inspect only the matching `deploy_ended` structured event;
- reduce structured reason fields to an allowlisted classification such as `BUILD_FAILED`, `NON_ZERO_EXIT`, `EARLY_EXIT`, `OOM_KILLED`, `TIMED_OUT`, `UNHEALTHY` or `EVICTED`;
- never print provider free-form reason text, raw logs, URIs, credentials or headers;
- run this diagnostic only after the canonical provisioner has already failed, and always preserve the original non-zero deployment result.

The diagnostic is not a bypass and cannot turn a failed deploy GREEN.

## Permanent regression / guard

Deterministic tests cover:

- exact-release deploy binding;
- wrapper/list response handling;
- allowlisted terminal-status validation;
- structured reason classification;
- rejection of unknown provider statuses;
- omission of arbitrary provider text from workflow output.

The canonical Phase 4 workflow compiles and runs these tests before any provider mutation, then invokes the diagnostic only inside the same accepted-main secret scope if provisioning fails.

## Future prevention rule

For external provider mutations, fail-closed status is necessary but not sufficient. Every finite provider wait loop must preserve a minimal, allowlisted, non-secret terminal classification that distinguishes build/config/start/health/capacity classes without copying arbitrary provider output into CI.

Provider diagnostic authority must stay in the same or narrower accepted-main secret boundary as the mutation itself. Do not create temporary secret-bearing workflows or expose provider credentials to PR code.

## Dependency/tooling knowledge change

Render's current public API exposes a finite deploy-status enum including `build_failed`, `update_failed`, `pre_deploy_failed`, `canceled` and `deactivated`, plus structured service events such as `deploy_ended`. Those structured fields are a safer engineering evidence surface than copying raw dashboard logs into GitHub Actions output.
