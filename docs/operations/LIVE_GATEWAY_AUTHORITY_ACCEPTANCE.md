# Live Gateway Authority Acceptance v1

## Purpose

This check verifies that the deployed Omni-CIO Gateway still exposes only the reviewed v9 GPT Action authority. It replaces the obsolete production-wide GET-only acceptance that became invalid once the reviewed conditional Sandbox/Real contours were enabled.

The checker performs only two public GET requests:

- `https://omni-cio-gateway.onrender.com/health`
- `https://omni-cio-gateway.onrender.com/openapi.json`

It never calls portfolio/account endpoints, never sends the Gateway API key and never invokes Sandbox or Real mutations.

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

## Workflow

`.github/workflows/live-gateway-authority.yml` runs:

- manually with `workflow_dispatch`;
- once per day;
- on pull requests that modify this acceptance boundary.

It uses read-only repository permissions, pinned GitHub Actions and hash-locked runtime dependencies. No repository secret is required.

Command:

`python scripts/check_live_gateway_authority.py`

## Failure handling

A failure means the deployed OpenAPI authority no longer matches the reviewed v9 contract or the deployment version/configuration is inconsistent. Do not weaken the allowlist and do not submit a broker operation to diagnose it. Compare the failed error code with current `main`, Render deployment state and `gpt/ACTIONS_CATALOG.md`.

## Safety invariants

This live check must never:

- send a Gateway/Broker token;
- call a protected Action;
- prepare or execute a Sandbox/Real trade;
- alter feature flags or limits;
- infer a fill/order state;
- broaden the reviewed Action allowlist without a separate reviewed change.
