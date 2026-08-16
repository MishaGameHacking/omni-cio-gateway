# Live Gateway Authority Acceptance v1

## Purpose

This check verifies that the deployed Omni-CIO Gateway still exposes only the reviewed v9 GPT Action authority. It replaces the obsolete production-wide GET-only acceptance that became invalid once the reviewed conditional Sandbox/Real contours were enabled.

The checker performs only two public GET requests:

- `https://omni-cio-gateway.onrender.com/health`
- `https://omni-cio-gateway.onrender.com/openapi.json`

It never calls portfolio/account endpoints, never sends the Gateway API key and never invokes Sandbox or Real mutations.

## Current evidence-routing state — 2026-08-16

The current live-evidence state is:

`DEFERRED_NO_TRUSTED_ZERO_COST_ROUTE_NOT_PASS`

This is an explicit degraded evidence state. It **must not be treated as live PASS**.

The OWNER-observed GitHub-hosted Actions budget is currently blocked by the zero-budget hard stop. A governance diagnostic also proved that the Lenovo Personal Node is not a semantically equivalent external observation point for this check: DNS resolution of the protected Render host succeeds, but the node cannot establish the required TCP/443 path and HTTP fails at connect time.

Consequently:

- the real `Live Gateway Authority Acceptance` remains a **manual hosted acceptance** workflow;
- automatic daily execution is suspended while there is no trusted runnable independent route;
- pull requests that change this evidence boundary run `V10 Live Gateway Authority Contract` on Lenovo instead;
- that PR contract validates source/routing/non-fabrication and explicitly does not claim that the deployed V9 endpoint was observed successfully;
- a governance-only change that does not modify V9 runtime/deployment/Action authority does not require unrelated deployed-live evidence to become PASS before merge;
- any V9 runtime/deployment/Action-authority release that owns production acceptance remains blocked until actual hosted live acceptance succeeds;
- restoring schedule or automatic live PR probing requires a reviewed GREEN routing change after trusted-route and hosted-capacity re-verification.

This preserves the protected V9 rollback while accurately distinguishing source correctness from the freshness of external deployed evidence.

## Health gates

Acceptance requires:

- `status=ok`;
- deployed version equals repository `APP_VERSION`;
- legacy `trading_methods` marker remains `false`;
- production read-only T-Invest credential is reported configured as a boolean only;
- Gateway Bearer credential is reported configured as a boolean only.

No secret value is fetched or logged.

## OpenAPI authority gates

The effective deployed schema is validated against the reviewed catalog in `gpt/ACTIONS_CATALOG.md`:

- all 14 baseline GET Actions must exist;
- no operationId outside the reviewed baseline/Sandbox/Real sets may be exposed;
- every reviewed operationId must use its canonical HTTP method and path;
- Sandbox may be fully absent or expose the complete reviewed 8-operation virtual surface;
- Real may be absent, expose status-only while fail-closed, or expose the complete reviewed 4-operation ready surface;
- reviewed consequential mutation Actions must retain `x-openai-isConsequential: true`;
- no PUT/PATCH/DELETE Action is accepted;
- withdrawal/transfer, margin/short, stop-order, replace-order and async-post paths are rejected;
- the OpenAPI server must be the approved HTTPS Gateway host;
- health and OpenAPI application versions must match the repository expectation.

This does **not** authorize a trade. It verifies only what operations the GPT could call.

## Relationship to baseline read-only contracts

`ReadOnlyReleaseManifestV1` and its focused tests remain useful for the baseline mode where conditional Sandbox/Real surfaces are disabled. They are no longer used as the scheduled acceptance of a production deployment that intentionally publishes reviewed protected execution Actions.

The production authority source is the effective `/openapi.json`, bounded by `gpt/ACTIONS_CATALOG.md` and the server-side confirmation/idempotency contracts.

## Workflows

### Actual deployed acceptance

`.github/workflows/live-gateway-authority.yml` preserves the real network acceptance and currently runs only with `workflow_dispatch`.

The actual live job uses a GitHub-hosted runner because the evidence is intentionally independent of the Personal Node. While the zero-budget hard stop remains current, engineering must not dispatch it merely to create a known billing RED. It becomes required when its owning V9 runtime/deployment/Action-authority acceptance is actually needed and trusted hosted capacity has been restored or explicitly approved.

Command:

`python scripts/check_live_gateway_authority.py`

### Pull-request evidence-routing contract

`.github/workflows/v10-live-gateway-authority-contract.yml` runs on pull requests that change this acceptance/routing boundary. It executes on the Lenovo continuity lane and validates:

- the source-controlled capacity state;
- that real live acceptance remains hosted and manual while deferred;
- that automatic scheduled live execution is absent during the known blocked state;
- that the PR check reports the live evidence as deferred rather than PASS;
- that the tracked read-only live authority assets remain intact.

A successful `V10 Live Gateway Authority Contract` is a successful **contract/routing** check only. It is not deployed-live acceptance.

## Failure handling

A real hosted acceptance failure means the deployed OpenAPI authority no longer matches the reviewed v9 contract, the deployment version/configuration is inconsistent, or the trusted hosted path cannot obtain the required public evidence. Do not weaken the allowlist and do not submit a broker operation to diagnose it.

A routing-contract failure means the source-controlled evidence policy is inconsistent or could fabricate/drop required evidence. Fix the routing/contract rather than relabeling the failure as PASS.

## Safety invariants

This live check must never:

- send a Gateway/Broker token;
- call a protected Action;
- prepare or execute a Sandbox/Real trade;
- alter feature flags or limits;
- infer a fill/order state;
- broaden the reviewed Action allowlist without a separate reviewed change.
