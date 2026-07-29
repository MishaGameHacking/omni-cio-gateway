# Read-Only GPT Actions Release Contract v1

## Scope

PR-18 turns the effective FastAPI OpenAPI document into a machine-checked
read-only release contract for the Omni-CIO GPT Actions surface.

The checker imports the real `app:app`, calls the actual custom OpenAPI builder
and inspects the resulting schema. It does not maintain a second handwritten
list of routes or operation IDs.

## Official GPT Actions basis

OpenAI currently documents that a GPT Action is configured from authentication
information and an OpenAPI JSON or YAML schema. The schema defines the server,
endpoints, parameters and operation IDs available to ChatGPT. The configured
Action should be exercised in the GPT editor Preview before sharing or
publishing.

A GPT may use Apps or Actions, but not both at the same time. A publicly shared
GPT with Actions must have a valid privacy-policy URL.

These editor and publishing requirements remain user-side configuration work;
PR-18 validates the gateway contract that will be supplied to the editor.

## CI gate

Regression Shield now runs:

`python scripts/check_read_only_release_contract.py`

The command prints a deterministic manifest of the effective release surface
and fails before pytest if any hard invariant is broken.

## Checked invariants

### Version and entrypoint

- stable entrypoint is `app:app`;
- application version is exactly `3.9.1`;
- OpenAPI major version is 3.

### Server boundary

- at least one server is present;
- every server uses HTTPS;
- every server host is explicitly approved;
- URL credentials, query parameters and fragments are forbidden;
- duplicate normalized server URLs are forbidden.

The current approved Action host is:

`omni-cio-gateway.onrender.com`

### Action surface

- only HTTP GET operations may be exposed in the schema;
- every operation requires a non-empty unique `operationId`;
- `/health` is the only public Action;
- every other Action must declare OpenAPI authentication;
- every route is classified as either public or authenticated.

### Forbidden surfaces

The release fails when a path or operation ID exposes markers associated with:

- order creation or submission;
- order replacement or cancellation;
- execution or confirmation;
- money withdrawal;
- money or securities transfer.

The checker does not ban historical words such as `buy`, `sell`, `trade` or
`withdrawal` inside read-only analytics responses. It inspects only paths and
operation IDs, preventing false positives on portfolio history.

## Manifest

A successful check produces `ReadOnlyReleaseManifestV1` containing:

- generation timestamp;
- app and OpenAPI versions;
- stable entrypoint;
- approved servers;
- actual action paths, methods and operation IDs;
- public/authenticated classification;
- reconciled action counts;
- explicit GET-only, unique-operation-ID and approved-server assertions;
- `forbidden_surface_count=0`;
- `trading_methods=false`.

The manifest contains no token, account, portfolio or request data.

## Tests

Acceptance tests cover:

- the effective production OpenAPI schema;
- a synthetic POST Action;
- a GET Action with a forbidden execution operation ID;
- duplicate operation IDs;
- a private Action without authentication;
- a public health Action incorrectly requiring authentication;
- HTTP, foreign-host, credential-bearing and query-bearing server URLs;
- missing and duplicate servers;
- app/OpenAPI version drift;
- absence of write/execution markers in the final manifest.

## Privacy-policy and editor Preview

PR-18 cannot configure the user's GPT editor or publish a privacy policy on the
user's behalf. Before public sharing, the user must provide a valid privacy
policy URL and test each imported Action in the GPT editor Preview according to
current OpenAI product requirements.

This does not block private repository development or the read-only gateway
contract itself.

## Rollback

Revert the PR merge commit. The only workflow change is removal of the release
contract check. No runtime route, OpenAPI response, Render service, secret or
broker migration is required.
