# Omni-CIO V10 hosted release alignment standard

Status: **FOCUSED DEFECT #396 — EFFECTIVE WHEN MERGED TO PROTECTED `main`**  
Scope: the accepted zero-cost Render/Neon hosted technical preview only; this is not public-production activation.

## Purpose

GitHub `main` is engineering authority, but a source merge and a running hosted release are different states. The controlled Render preview intentionally has direct provider auto-deploy disabled so provider mutation occurs only through the repository-controlled deployment workflow after exact-main Regression Shield and the zero-cost provider boundary.

Therefore a successful exact-main `push` workflow batch does not by itself prove that the hosted preview is running that SHA.

## Required evidence chain

When the hosted technical preview is applicable, post-merge runtime evidence is:

`accepted main -> exact-main Regression Shield SUCCESS -> V10 Phase 4 Free Preview Deploy terminal state -> V10 Hosted Release Alignment SUCCESS`

`V10 Hosted Release Alignment` is read-only and secret-free. It probes only the canonical public `/healthz` endpoint and requires:

- HTTP 200 without redirects;
- `status=ok`;
- `database=READY`;
- `synthetic_preview=true`;
- `release_sha` exactly equal to the expected 40-character accepted-main SHA.

A mismatch is `PREVIEW_RELEASE_SHA_DRIFT` and is not GREEN runtime evidence.

The alignment workflow runs after every Phase-4 deployment workflow completion regardless of whether that deployment succeeded or failed. It also runs on a bounded daily self-hosted schedule so a manual rollback or other provider-side release drift does not wait for the next repository merge to become visible.

If `main` advances between an older deployment trigger and its alignment job, that old job reports `HOSTED_RELEASE_ALIGNMENT=SUPERSEDED_BY_NEWER_MAIN` and makes no current-runtime PASS claim. The newer `main` SHA owns its own Regression Shield -> deploy -> alignment chain; only that latest applicable chain may prove the site current.

To close the probe/PASS-publication race, successful probe output is withheld until a post-probe main recheck. The workflow re-fetches `main` after the runtime probe and publishes the captured `PREVIEW_RELEASE_ALIGNMENT=PASS` only when the branch still equals `EXPECTED_MAIN_SHA`. If `main` advanced during the probe, the captured PASS is suppressed and the run reports `HOSTED_RELEASE_ALIGNMENT=SUPERSEDED_BY_NEWER_MAIN` instead.

## Controlled deployment boundary

Do not fix drift by enabling Render direct `On Commit` auto-deploy. The accepted preview provisioner keeps `autoDeploy=no` intentionally. This preserves:

- exact-main Regression Shield before provider mutation;
- fresh zero-charge OWNER attestation;
- Neon free-plan verification;
- exact-SHA deploy identity;
- provider/payment fail-closed behavior.

A stale or missing `RENDER_ZERO_CHARGE_ATTESTATION` must continue to block deployment. The alignment guard must still run and expose the stale release identity without receiving Render/Neon credentials.

## Post-merge acceptance rule

For an accepted-main change that triggers the hosted preview chain, an inventory limited to `event=push` is incomplete. The applicable downstream `workflow_run` chain must also reach terminal state.

Applicable downstream `queued`, `pending`, `in_progress`, `failure`, `cancelled`, `timed_out`, `action_required`, `stale`, `neutral` or `skipped` states/conclusions are not accepted post-merge runtime evidence. The latest applicable hosted-preview chain is accepted only when its required downstream alignment concludes `success` on the exact expected SHA.

Repository authority and hosted-runtime alignment must be reported separately when they differ. Do not say the hosted site is current unless the latest applicable alignment gate succeeds on the exact expected SHA. A superseded older run is neither drift evidence nor current-runtime PASS evidence.

If the deployment is blocked by a genuinely non-delegable OWNER/provider condition, record that blocker explicitly and keep runtime alignment RED/stale until the real condition is resolved. Do not fabricate a provider attestation or weaken the gate to remove the RED result.

## Safety invariants

This guard does not change:

- protected V9 `app:app` production/recovery;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- zero recurring-cost authority;
- secret/private-data exclusion;
- public-production/provider/legal activation gates;
- `WEB-VISUAL-INTEGRATED` OWNER START requirement.
