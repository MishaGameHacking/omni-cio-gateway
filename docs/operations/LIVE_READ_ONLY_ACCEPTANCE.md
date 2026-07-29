# Live Read-Only Acceptance v1

## Purpose

This check verifies that the deployed Omni-CIO Gateway still matches the reviewed
read-only release contract. It complements Render's process health check with an
application-level inspection of the public `/health` response and the effective
`/openapi.json` document.

The checker does not call portfolio, operations, market, preview or broker
endpoints. It does not send an API key and does not access account data.

## Endpoints

Only two public GET requests are permitted:

- `https://omni-cio-gateway.onrender.com/health`
- `https://omni-cio-gateway.onrender.com/openapi.json`

Redirects are rejected. The base URL must use HTTPS, contain no credentials,
query, fragment, non-standard port or extra path, and use the approved Render
host.

## Health gates

The live release fails acceptance unless:

- `status` is `ok`;
- the deployed version equals the repository `APP_VERSION`;
- `trading_methods` is exactly `false`;
- the T-Invest token is reported as configured using a boolean only;
- the gateway API key is reported as configured using a boolean only;
- the required read-only capabilities are present.

The response is never allowed to expose the actual token or key.

## OpenAPI gates

The fetched OpenAPI document is passed through the same
`ReadOnlyReleaseManifestV1` inspection used by Regression Shield. Therefore the
live schema must retain:

- OpenAPI 3;
- the approved HTTPS server;
- GET-only Actions;
- unique non-empty `operationId` values;
- authentication for every Action except `/health`;
- zero order execution, cancellation, withdrawal or transfer surfaces;
- `trading_methods=false`.

The OpenAPI server URL must exactly equal the checked live base URL.

## Network safety

The HTTP loader:

- uses the Python standard library;
- sends only `Accept` and a non-secret user-agent header;
- has a bounded response size;
- requires JSON content;
- decodes UTF-8 strictly;
- rejects redirects at the acceptance boundary;
- retries only timeouts, connection failures, HTTP 429 and HTTP 5xx;
- never retries a validation failure;
- never logs response bodies or exception messages containing remote content.

## GitHub workflow

`.github/workflows/live-read-only-acceptance.yml` runs:

- manually through `workflow_dispatch`;
- once per day on a schedule;
- in a pull request when the live acceptance workflow, contracts, verifier,
  CLI or focused tests change.

The path-filtered pull-request trigger provides actual production evidence while
the acceptance boundary itself is being modified. Ordinary analytics and model
PRs are not coupled to production availability.

The workflow uses read-only repository permissions, pinned GitHub Actions and
hash-locked runtime dependencies. It requires no repository secret.

The command is:

`python scripts/check_live_read_only_release.py`

The optional `OMNI_LIVE_BASE_URL` environment variable may select another
explicitly approved deployment in a future reviewed change. The current
allowlist contains only `omni-cio-gateway.onrender.com`.

## Relationship to Render health checks

Render uses `healthCheckPath: /health` to determine whether a web-service
instance is responsive. A successful HTTP status alone does not prove that the
correct application version, Action schema or read-only boundary is deployed.
This acceptance layer verifies those stronger invariants after deployment.

## Failure handling

A failure means the deployed service must not be treated as an accepted
Omni-CIO release. It does not automatically redeploy, modify secrets, call the
broker or change traffic. Review the failed error code, the Render deployment
state and the current `main` commit before taking corrective action.

## Rollback

Revert the PR merge commit to remove the checker and scheduled workflow. This PR
does not alter FastAPI routes, Render commands, environment variables, broker
permissions, OpenAPI responses or account data.
