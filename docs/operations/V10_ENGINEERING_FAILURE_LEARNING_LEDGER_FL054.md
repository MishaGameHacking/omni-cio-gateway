# FL-054 — Post-merge acceptance must traverse downstream deployment event topology

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR FOCUSED DEFECT #396; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-27**  
WP / PR / reference: **post-Amendment-13 hosted release drift / issue #396**

## Symptom / failing gate

Protected `main` advanced to `20cb229327701d1b61be1ac3272727a16bc8b5e3` and all 11 exact-main `push` workflows completed `success`, but the canonical zero-cost hosted technical preview still served the prior accepted Phase-5 SHA `bb15739acf82ded8eafb6d006cf222fb3988770d`.

The downstream `V10 Phase 4 Free Preview Deploy` run `33067259377` did start for exact main `20cb229...`, but failed at `Enforce zero-charge provider boundary` with sanitized code `RENDER_ZERO_CHARGE_ATTESTATION_STALE`. Provider mutation and the actual Render deploy were correctly skipped.

## Root-cause analysis

Two independent facts combined:

1. The zero-cost policy intentionally makes the OWNER Render no-payment-method attestation valid for at most 24 hours. The stored attestation had expired, so the deployment workflow correctly failed closed.
2. Final post-merge acceptance inventory was filtered to exact-SHA `push` workflows. The deployment is a later `workflow_run` child of Regression Shield, so it was outside that inventory and its RED conclusion was not included before the repository handoff was declared complete.

Render direct auto-deploy was not malfunctioning. The accepted provisioner intentionally requires `autoDeploy=no`; GitHub controls exact-SHA deployment after safety gates.

## Blast radius searched

Repository search found the existing Phase-4 deployment workflow as the only accepted `workflow_run` consumer before this correction. No parallel Web deployment stack or second Render service is introduced.

The directly coupled surfaces are:

- exact-main Regression Shield producer;
- `.github/workflows/v10-phase4-free-preview-deploy.yml` downstream deployment consumer;
- Render `autoDeploy=no` service contract in `scripts/provision_v10_render_neon_preview.py`;
- canonical `/healthz.release_sha` producer in `apps/api/hosted_preview.py`;
- post-merge acceptance/handoff logic that inventories Actions runs.

Adjacent failure modes include a provider-side manual rollback, a deployment failure after a successful merge, a stale/cold hosted runtime, and an acceptance query that filters by event type rather than traversing the applicable workflow chain.

## Why preflight missed it

Pre-merge verification correctly proved the code/governance head. Post-merge Regression Shield also correctly proved exact main. The missing assumption was that repository post-merge GREEN implied hosted-preview convergence even though the deployment trigger occurs only after Regression Shield and uses a different GitHub event type.

The acceptance process had exact-SHA rigor but an incomplete event-topology boundary.

## Corrective change

Focused defect #396 adds a read-only hosted-release alignment guard that:

1. runs after every Phase-4 deployment workflow completion regardless of upstream conclusion;
2. independently compares the expected main SHA with canonical `/healthz.release_sha`;
3. requires healthy database/synthetic-preview contract fields as well as the exact SHA;
4. rejects redirects, malformed responses and bounded network/provider failures;
5. performs a bounded daily self-hosted recheck to expose manual/provider-side drift;
6. uses no Render, Neon, broker or product secrets.

The controlled deployment and zero-cost attestation requirements remain unchanged.

## Permanent regression / guard

For any accepted-main change that triggers a downstream deployment/runtime workflow, final acceptance inventory must follow the complete applicable event chain, not only the initiating `push` runs.

When an external runtime exposes accepted release identity, a secret-free exact-release alignment check must remain available and must be RED on SHA mismatch. Repository authority and runtime alignment are separate facts until both are proven.

## Future prevention rule

Never infer `site == main` from a green source/Regression-Shield batch. Prove deployment/runtime identity from the downstream workflow and the runtime's own release endpoint. If the deployment is blocked by a non-delegable provider condition, report that blocker and the stale runtime explicitly rather than declaring the whole operational handoff complete.

Do not enable provider direct auto-deploy merely to hide a controlled-deployment RED condition.

## Dependency/tooling knowledge change

No dependency upgrade is required. The relevant GitHub Actions behavior is event topology: `workflow_run` fires when the named upstream workflow completes, including unsuccessful conclusions unless the downstream job adds a success-only condition. The correction intentionally uses that behavior to detect stale hosted runtime after failed deployment as well as after successful deployment.
