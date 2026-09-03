# V10 Engineering Failure Learning Ledger — FL087

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, CF-D exact-main
production release and Neon provider-authority boundary.

Owning security defect: `#442`.

## Failure observed

After PR #441 was accepted into exact main
`96e26827a29afff7b7ea443e629e5c76652787c9`, all 11 required post-merge push
workflows completed successfully and the automatic CF-D production release started.

The source correction in #441 correctly consumed the official Neon GitHub integration
project selector as a repository variable. GitHub Actions then rendered that non-secret
variable value in the step environment section of the job log before application code
executed.

The provider identifier value is intentionally not reproduced in this ledger.

The same fresh run remained fail-closed at Neon authority: credential-only and
organization/project read surfaces returned HTTP 403. No staging database mutation,
Cloudflare production promotion, Custom Domain mutation or canonical live acceptance
was performed.

## Root cause class

`GITHUB_ACTIONS_PROVIDER_VARIABLE_LOG_EXPOSURE`

The repository correctly distinguished a non-secret Project ID from an API credential,
but incorrectly assumed that "non-secret" also meant "permitted in public engineering
logs". Direct `${{ vars.NEON_PROJECT_ID }}` expansion into a step environment caused
GitHub Actions to render the identifier before any in-process masking could run.

Post-hoc `add-mask` is therefore insufficient: the identifier must never enter the
runner-visible workflow environment in the first place.

## Blast radius

Direct project-ID environment bindings existed in:

- `.github/workflows/v10-cloudflare-provider-readiness.yml`;
- `.github/workflows/v10-cloudflare-candidate-deploy.yml`;
- `.github/workflows/v10-cloudflare-production-release.yml`.

The exact-project runtime itself remains fail-closed and still validates project name,
organization ownership, PostgreSQL 18 and Frankfurt region before provider mutation.

The existing `NEON_API_KEY` and protected organization binding remain Secrets. This
focused correction does not redesign organization authority and does not grant new
provider permissions.

## Correction

Active CF-C/CF-D workflows no longer inject any Project ID secret or variable into the
runner environment.

A privacy-safe provider resolver now:

1. reads only the existing Neon API credential and protected organization binding;
2. first performs a read-only project query scoped to the protected organization and the
   exact canonical project name `omni-cio-v10-preview-frankfurt`;
3. if and only if that first list operation returns HTTP 403, retries the same read-only
   canonical-name query without `org_id` so a project-scoped Neon integration key can
   expose only the projects granted by its credential scope;
4. never downgrades a non-403 failure to that credential-scoped fallback;
5. paginates the provider result with a bounded maximum and rejects repeated cursors,
   incomplete evidence or multiple exact-name matches;
6. reuses the existing runtime validator to require the protected organization,
   PostgreSQL 18 and `aws-eu-central-1` even after credential-scoped fallback;
7. masks the discovered project ID inside the Python process before any exact-project
   request;
8. uses the identifier only in process memory for the existing exact-project probe or
   runtime provisioner;
9. restores any temporary process environment binding before exit;
10. emits only categorical/status evidence, never provider identifiers.

The official Neon GitHub integration may continue to maintain its repository variable,
but the active release path no longer expands that value into Actions logs or requires
manual project-ID copying.

## Regression invariant

Deterministic guards/tests require that:

- active readiness, candidate and production workflows contain neither
  `secrets.NEON_PROJECT_ID` nor `vars.NEON_PROJECT_ID`;
- no active workflow assigns `NEON_PROJECT_ID` or `NEON_PROJECT_ID_VALUE`;
- Neon API credentials remain secret-only;
- exact canonical discovery is GET-only and first attempts the protected organization;
- credential-scoped fallback is permitted only after a 403 from the organization-scoped
  list operation;
- non-403 provider failures never downgrade to fallback discovery;
- pagination is bounded and cursor loops fail closed;
- zero or multiple canonical-name matches fail closed;
- organization, PostgreSQL 18 and Frankfurt drift fail closed after either discovery
  mode;
- the discovered Project ID is masked before exact-project reads;
- temporary in-process binding is restored after provisioning;
- diagnostics expose only status/category evidence;
- the existing exact-project authority gate still precedes provider mutation.

## Permanent learning

- Provider documentation classifying metadata as non-secret does not override the
  repository's stricter privacy/no-identifier-log policy.
- GitHub Actions expressions expanded into step `env` can become log-visible before
  application code has an opportunity to mask them.
- Sensitive or private routing metadata should be derived inside the process from
  already-authorized provider reads when deterministic fail-closed discovery is
  available.
- Project-scoped credentials need a narrow read-only discovery path, but fallback must
  be explicit, status-classified and followed by exact organization/runtime validation.
- Provider discovery must never silently broaden mutation authority: exact canonical
  identity and runtime constraints must still be proven before mutation.
- A source privacy correction does not resolve an external credential failure. The
  separate CF-D blocker remains open until a fresh provider credential returns real
  read authority.

## Security and authority invariants preserved

- protected V9 `app:app` remains unchanged;
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged;
- broker write remains OFF;
- `trading_methods=false` remains unchanged;
- `REAL_TRADING_ENABLED=false` remains unchanged;
- no Neon API key, provider identifier value, database DSN or tenant-private payload is
  committed or logged;
- no provider mutation is authorized by this source correction itself;
- production remains behind exact-main post-merge, provider authority, staging,
  rollback and live-acceptance gates.
