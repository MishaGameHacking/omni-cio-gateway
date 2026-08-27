# FL-055 — Provider preflight must preserve safe authentication classification

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR FOCUSED DEFECT #396; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-27**  
Reference: **post-merge hosted-preview recovery after PR #397 / issue #396**

## Symptom / failing gate

After the OWNER refreshed the accepted Render zero-charge attestation, exact-main deployment run `33090589119` advanced through Regression Shield and deterministic source validation but still stopped before provider mutation at `Enforce zero-charge provider boundary`.

The only emitted code was `NEON_API_KEY_INVALID_OR_INSUFFICIENT`. The downstream hosted-release alignment then correctly remained RED because the public technical preview still served the older accepted SHA.

## Root cause

Two facts are distinct and must not be conflated:

1. the live Neon credential presented by the workflow was rejected by the provider as an authentication/authorization failure, so deployment correctly failed closed;
2. the preflight implementation collapsed HTTP 401 and 403 into one error code and omitted the already-sanitized HTTP status from CLI output, preventing deterministic distinction between invalid/revoked credentials and insufficient credential authority.

The provider credential itself is external configuration. Engineering cannot manufacture, recover or print a real secret in source, GitHub comments, CI logs or chat.

## Blast radius searched

The directly coupled surfaces were reviewed:

- `scripts/check_v10_zero_cost_provider_boundary.py` — read-only Neon free-plan preflight;
- `.github/workflows/v10-phase4-free-preview-deploy.yml` — consumer that must stop before provider mutation;
- `scripts/provision_v10_render_neon_preview.py` — downstream provider client that uses the same Neon credential only after the boundary passes;
- `scripts/check_v10_hosted_release_alignment.py` — downstream read-only runtime detector, whose RED is a symptom rather than the provider-auth root cause.

Repository search also found analogous urllib exception tuples in other verification scripts. They are tracked as analogous quality debt but are not silently expanded into this provider-auth correction unless their owning behavior is materially coupled.

## Why preflight missed it

The existing deterministic zero-cost tests covered fresh/stale attestation, free/paid organization plans, redirects and secret non-disclosure, but did not cover distinct Neon 401 versus 403 outcomes, bounded transient provider retries or response-size limits.

The live credential cannot be exercised in ordinary PR validation without crossing the protected provider-secret boundary, so the deterministic contract must preserve enough sanitized failure information to make the first real-provider failure actionable.

## Corrective change

The focused correction:

1. keeps the preflight read-only and before every provider mutation;
2. distinguishes `NEON_API_KEY_INVALID` (401) from `NEON_API_KEY_INSUFFICIENT` (403);
3. preserves safe HTTP status in the CLI error while never printing provider response bodies or the token;
4. adds bounded retry for transient GET/network failures only;
5. bounds the organization response size before JSON processing;
6. uses the common `OSError` network boundary instead of redundant exception subclasses;
7. adds deterministic regression tests for authentication classification, transient retry exhaustion, oversized responses and secret non-disclosure.

## Permanent regression / guard

Provider preflight tests must prove that authentication/authorization failures remain distinguishable using sanitized codes/status only, transient read-only failures have bounded retries, provider bodies are never echoed, and an external credential failure never reaches a mutation step.

## Future prevention rule

Fail-closed is necessary but not sufficient for operability. A protected provider gate must fail with the narrowest safe diagnostic classification available so an external configuration problem is not mistaken for application-code failure or vice versa.

Do not weaken the zero-charge gate, enable Render direct auto-deploy, fabricate provider evidence or retry non-idempotent provider mutations merely to clear a RED workflow.

## Dependency/tooling knowledge change

Neon API access uses Bearer authentication. The accepted organizations endpoint is a read-only GET and can be retried only for bounded transient transport/provider statuses; authentication and authorization failures are terminal until the real credential/configuration is corrected outside source control.
