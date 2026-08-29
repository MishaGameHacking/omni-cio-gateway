# FL-059 — Provider-authority retirement must migrate regression consumers with producers

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR PR #408; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-29**  
WP / PR / reference: **Cloudflare platform authority transition / PR #408**

## Symptom / failing gate

After the focused Cloudflare authority branch had passed its governance/focused DRAFT checks, the authoritative Windows Regression Shield still failed with nine deterministic pytest assertions.

The failures were not runtime/provider failures. They were repository-consistency failures: two protected V9 navigation markers had been lost while live guidance was compressed, and seven historical tests still expected the retired Render Phase-4 / hosted-release workflows to auto-trigger or execute provider operations.

## Root cause

The provider-authority blast-radius review updated the workflow producers and the new Cloudflare authority guard, but did not enumerate every full-suite consumer that asserted the old Render workflow topology or every long-lived V9 navigation marker preserved by repository-hygiene tests.

This created two adjacent failure modes at once:

1. canonical live guidance remained semantically correct but lost exact protected historical evidence (`WP0–WP15` / `controlled maintenance`);
2. legacy regression consumers treated the old automatic Render workflows as current behavior even though Amendment 14 intentionally made those workflows manual-only fail-closed provenance stubs.

## Blast radius searched

The correction search covered:

- `.github/workflows/v10-phase4-free-preview-deploy.yml`;
- `.github/workflows/v10-hosted-release-alignment.yml`;
- `tests/test_v10_hosted_release_alignment.py`;
- `tests/test_wp22a_phase4_deploy_contract.py`;
- `tests/test_wp22a_phase4_provisioner_import_path.py`;
- `tests/test_wp22a_phase4_render_deploy_diagnostic.py`;
- `tests/test_wp22a_phase4_runtime_role_retry.py`;
- `tests/test_post_v9_repository_hygiene.py`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `CONTRIBUTING.md`;
- the Cloudflare authority checker/tests and directly related workflow-governance consumers.

Historical standalone Render/Neon unit/security tests remain valid evidence for archived code and are not deleted merely because the active workflow authority changed.

## Why preflight missed it

Focused preflight exercised the new Cloudflare governance checker and directly changed tests, but the branch was published before a complete full-suite Regression Shield had been used as a consumer inventory check. Repository search also focused on active provider/config references and missed several text-only workflow assertions in historical tests.

A review bot then proposed weakening the V9 hygiene assertions instead of restoring the historical markers. That proposal was rejected: GREEN must come from correcting canonical evidence and consumer semantics, not from lowering a protected regression expectation.

## Corrective change

- restore the protected V9 `WP0–WP15` and `controlled maintenance` evidence in canonical live guidance;
- keep the V9 repository-hygiene test strict;
- migrate workflow-activation assertions to the Amendment-14 contract: manual-only historical stubs, no `workflow_run`, no schedule, no Render/Neon secret references, no provider mutation, explicit retired marker and fail-closed exit;
- keep standalone historical provisioner/diagnostic/runtime-role tests intact where they still verify archived code behavior;
- do not re-enable Render provider actions merely to satisfy old tests.

## Permanent regression / guard

The Cloudflare authority checker rejects reintroduction of `workflow_run:`, `schedule:`, `RENDER_API_KEY` and `NEON_API_KEY` in the retired workflows and requires their Amendment-14 retired markers / fail-closed exits.

The migrated workflow tests additionally prove that archived provisioner/diagnostic/runtime-role code is not invoked by the retired workflow while the standalone historical tests remain executable in the full suite.

The V9 hygiene test continues to require the protected historical navigation markers rather than being weakened.

## Future prevention rule

Any authority/provider workflow retirement must inventory **both producers and every regression consumer** before publishing the verification head. Search not only active provider strings but also workflow names, trigger names, step names, script/module invocations, secret names and long-lived status markers.

Before declaring such a branch preflight-ready, run the full Regression Shield (or an equivalent complete consumer set) on the trusted runner when feasible. Focused governance tests are necessary but are not sufficient evidence that all historical consumers were migrated.

## Dependency/tooling knowledge change

None. No dependency or provider-runtime upgrade is required. This is a regression-consumer/governance synchronization correction; Cloudflare provider mutation remains outside PR #408.
