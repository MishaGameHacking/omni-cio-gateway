# V10 Engineering Failure Learning Ledger — FL092

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, CF-D focused recovery PR `#450` after accepted main `2491ad5fb95321970d63e41ae36d3c30d04dbb3c`.

This entry records the exact-head review/analyzer failure exposed after the first trusted-Worker egress correction. It does not authorize public multi-user activation, Telegram/VK activation, broker write, Real execution or a new Work Package.

## Symptom / failing gates

Exact PR head `ee28e22246dcaad388c2e4f21505867b2913f1bb` completed the repository-owned fast checks that had reached terminal state, but SonarQube Cloud failed the Quality Gate with **Security Rating on New Code = B** where A is required.

The four surfaced annotations were concrete rather than an opaque provider failure:

- re-export `ContainerProxy` directly from `@cloudflare/containers` instead of importing then re-exporting it;
- the Container bootstrap virtual-hop literal used `http://` and triggered the insecure-HTTP security rule;
- the trusted Worker destination selector used a nested ternary;
- the same selector retained a nullable branch that made the expression unnecessarily complex.

Independent Files-changed review also found two adjacent defects in the same block:

- the Worker buffered the branch-metadata response without an explicit response-size ceiling;
- the Python staging adapter retained branch/cell helpers and parameters after destination authority moved to the Worker, but the then-current route no longer used them, making the startup contract misleading.

## Root cause

`CF_D_EGRESS_RUNTIME_SECURITY_CONTRACT_NOT_FULLY_EXPRESSED_IN_CODE`

Cloudflare Containers documents that virtual HTTP calls to an `outboundByHost` handler remain on the same machine and are protected by the platform networking stack. That platform fact made the existing virtual hop safe in deployment, but the source still expressed an insecure-looking scheme that a context-free security analyzer correctly treated conservatively. The code also did not yet opt into Cloudflare HTTPS interception, so there was no source-level TLS contract for the virtual hop.

Separately, the destination-policy selector and branch-response parser were functionally bounded enough for the happy path but were not expressed as the simplest deny-by-default policy table plus a streaming response budget.

## Why preflight missed it

Focused executable tests proved destination authority, route/method/SHA validation and trusted Worker network-sink allowlisting, but the preflight did not include the exact Sonar rule set and did not include an oversized SQL-over-HTTP branch response. The first bridge correction therefore proved the intended security semantics without proving analyzer-clean representation or response-memory bounds.

## Coherent correction

The correction changes the whole CF-D bootstrap transport block rather than suppressing individual warnings:

1. The Container now calls `https://cf-d-neon-bootstrap.internal/`.
2. `Backend.interceptHttps = true` opts into Cloudflare Containers HTTPS interception and the source directly re-exports `ContainerProxy`, as required by the platform contract.
3. The Python runtime creates an `ssl.SSLContext` from Cloudflare's runtime-generated `/etc/cloudflare/certs/cloudflare-containers-ca.crt`; when `OMNI_V10_CLOUDFLARE_RUNTIME=1`, a missing CA fails closed before any bootstrap request.
4. `httpx` keeps `trust_env=False` and redirect following disabled; no environment proxy or external CA shortcut is introduced.
5. The trusted Worker destination selector is a fixed `Map` from the two internal destination classes to exact URL-pattern/path policies, eliminating nullable/nested selection logic.
6. Neon branch metadata is read through a bounded stream with an 8 KiB ceiling before UTF-8/JSON parsing; oversized, invalid or malformed bodies fail closed.
7. The Python branch/cell derivation helpers are retained only as a request-time staging consistency check after exact-SHA and OIDC validation. A transient or missing branch context returns a bounded provider error for that bootstrap request rather than aborting application startup. Their result is not forwarded to the Container request and cannot select the Worker/provider destination.
8. Executable Node/Python regressions cover HTTPS-only virtual routing, forged-target rejection, oversized branch metadata, direct network-sink rejection, Cloudflare runtime CA fail-closed behavior and request-scoped branch-context failure without startup abort.

## Blast radius searched

Directly coupled surfaces reviewed:

- `apps/api/cf_d_database_bootstrap.py` staging-only bootstrap producer;
- `apps/api/cloudflare_runtime.py` route installation and runtime markers;
- `cloudflare/src/index.js` Container class and outbound handler registration;
- `cloudflare/src/cf-d-neon-bootstrap-egress.js` trusted database/function destination authority;
- Node and Python CF-D bootstrap regressions;
- existing PostgreSQL 18 staging runtime binding;
- short-lived GitHub OIDC forwarding;
- production secret bootstrap/reuse and downstream release ordering.

No Neon management API key/project/org authority, broker authority, product-auth bypass or global internet-policy widening is added.

## Permanent prevention rule

For future provider bridges, preflight must cover both executable authority semantics and the source-level transport/security representation seen by mandatory analyzers. Platform-internal plaintext that is secure only by provider-specific networking semantics should be replaced by an explicit TLS contract when the platform offers one and the runtime can fail closed on its trust anchor. Provider metadata responses used for authority derivation must have explicit byte ceilings before parsing.

Analyzer RED remains a merge blocker; suppressions, exclusions, Quality Gate weakening and secret reintroduction are forbidden recovery methods.
