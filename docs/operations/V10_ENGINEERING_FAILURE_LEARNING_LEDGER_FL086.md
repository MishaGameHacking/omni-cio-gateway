# V10 Engineering Failure Learning Ledger — FL086

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, CF-D exact-main
production release authority for the protected Neon PostgreSQL runtime.

Owning blocker: `#430`.

This entry records the repository-side integration defect discovered after the OWNER
installed the official Neon GitHub App and connected the canonical Neon project
`omni-cio-v10-preview-frankfurt` to `MishaGameHacking/omni-cio-gateway`.

## Failure observed

The accepted Cloudflare release workflows still consumed the Neon project binding from
`secrets.NEON_PROJECT_ID` and the candidate-delivery guard explicitly rejected
`vars.NEON_PROJECT_ID`.

That custody model conflicts with the official Neon GitHub integration contract. The
integration provisions the API credential as repository secret `NEON_API_KEY` and the
project selector as repository variable `NEON_PROJECT_ID`.

Repeated reruns of the pre-existing production workflow remained RED with sanitized Neon
HTTP `403` evidence. A rerun of an already-created workflow run is not accepted as proof
that a newly connected provider integration has been consumed. Fresh queued workflow
evidence is required after the repository uses the integration-created binding.

No failed run reached Neon database mutation, Cloudflare production promotion, Custom
Domain mutation or canonical live acceptance.

## Root cause class

`NEON_GITHUB_INTEGRATION_CUSTODY_CONTRACT_DRIFT`

The repository had preserved a defensive historical rule that all provider identifiers
must be GitHub Secrets. That rule was too broad for the provider-managed Neon GitHub
integration because the non-secret project selector is deliberately provisioned as a
GitHub Actions variable.

The security objective remains valid for actual credentials, but applying secret custody
to the project selector created a duplicate manual configuration surface and prevented
the official integration from becoming authoritative for that selector.

## Blast radius

Direct consumers reviewed and corrected together:

- `.github/workflows/v10-cloudflare-provider-readiness.yml`;
- `.github/workflows/v10-cloudflare-candidate-deploy.yml`;
- `.github/workflows/v10-cloudflare-production-release.yml`;
- `scripts/check_v10_cloudflare_candidate_delivery.py`;
- `tests/test_v10_cloudflare_neon_authority_preflight.py`;
- `tests/test_v10_cloudflare_candidate_provider.py`.

The Neon runtime provisioner remains fail-closed and still requires an exact project ID,
validates the exact configured project, preserves canonical project-name and Frankfurt
region constraints, preserves PostgreSQL 18 verification, and performs read authority
checks before mutation.

## Correction

The active CF-C/CF-D workflows now use:

- `secrets.NEON_API_KEY` for the credential;
- `vars.NEON_PROJECT_ID` for the provider-managed project selector;
- the existing protected `secrets.NEON_ORG_ID` for the organization binding in this
  focused correction.

`NEON_ORG_ID` custody is intentionally not redesigned in FL086. It is a separate
authority decision and must not be silently bundled into a project-binding correction.
If fresh provider evidence later proves that organization binding is the next blocker,
it requires its own root-cause analysis and focused correction.

The candidate-delivery guard now requires the official project variable and rejects a
return to `secrets.NEON_PROJECT_ID`. API key custody remains secret-only. Project ID is
never echoed, placed in source, or written to artifacts.

## Regression invariant

Deterministic tests require that:

- candidate and production Neon authority preflights read `NEON_API_KEY` from Secrets;
- the existing `NEON_ORG_ID` binding remains protected for this correction;
- all active Cloudflare workflows read `NEON_PROJECT_ID` from `vars`;
- `secrets.NEON_PROJECT_ID` is absent from the active integration paths;
- the exact-project read probe still precedes every provider mutation boundary;
- provider identity custody guards reject a stale project-ID Secret binding;
- no workflow prints Neon credential or identifier values.

Fresh exact-head CI and review evidence remains mandatory. The external blocker cannot be
closed from source inspection alone: after merge, a newly queued exact-main production
release must prove the provider-managed credential/project binding against real Neon.

## Permanent learning

- Provider-managed integrations must be consumed according to their documented custody
  contract instead of duplicated manually with a repository-specific convention.
- A non-secret routing identifier is not a credential. Protecting it as a Secret can add
  operational drift without increasing credential security.
- Secret custody remains mandatory for actual API credentials.
- Changing provider integration state requires a fresh queued workflow execution before
  acceptance; an older run or rerun is not substituted for fresh integration evidence.
- A repository correction may align configuration consumption but cannot fabricate
  provider authority. Real provider reads remain the acceptance boundary.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- broker write remains OFF.
- `trading_methods=false` remains unchanged.
- `REAL_TRADING_ENABLED=false` remains unchanged.
- no Neon API key, Cloudflare token, database DSN, provider identifier value or private
  tenant payload is committed or logged;
- no provider mutation is authorized by this source correction itself;
- exact-project authority remains fail-closed before staging or production mutation.
