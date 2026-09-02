# V10 Engineering Failure Learning Ledger — FL083

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, CF-D exact-main
production release authority for the protected Neon PostgreSQL runtime.

This entry records the second-stage diagnostic correction required after PR #434 made
Neon authority failures observable without exposing provider identifiers or secrets.

## Failure observed

Automatic production release run `33684572311` on exact accepted main
`e9316a920640ccef277e58a661cb86883f97eac9` proved the repository and Cloudflare
release authority chain, then failed before any provider mutation at the Neon
exact-project read gate.

The privacy-safe diagnostic emitted:

```text
organization_status=403
exact_project_status=403
exact_branches_status=403
canonical_query_status=SKIPPED
canonical_name_matches=UNKNOWN
configured_id_match=UNKNOWN
classification=ORG_SCOPE_UNAVAILABLE_EXACT_PROJECT_FORBIDDEN
```

The diagnostic remained secret-safe and fail-closed, but the classification was still
ambiguous. Neon explicitly documents that a project-scoped organization API key can
access only its specified project and cannot perform organization-related actions.
Therefore `GET /organizations/{org_id}` returning 403 is not, by itself, evidence that
the configured organization is wrong or unavailable to the credential identity.

Neon also documents `GET /users/me/organizations` as a credential-safe identity surface:
when called with an organization- or project-scoped API key, it returns the single
organization that owns the key. `GET /auth` separately reports the request authentication
method and associated identity. Those read-only surfaces can reduce the remaining
ambiguity without broad project enumeration and without weakening the exact-project
authority gate.

## Root cause class

`NEON_SCOPED_KEY_ORGANIZATION_IDENTITY_DIAGNOSTIC_GAP`

The diagnostic used organization-resource authorization as a proxy for credential
organization identity. That proxy is invalid for a legitimate project-scoped key,
because organization actions are intentionally outside that key's authority.

## Corrective invariant

After the existing exact-project authority proof has already failed:

- preserve that original failure as authoritative; diagnostics never turn RED into GREEN;
- read `GET /auth` and emit only the documented authentication-method enum, never
  `account_id` or `auth_data`;
- read `GET /users/me/organizations` and compare organization IDs only in memory;
- emit only whether protected `NEON_ORG_ID` is present in the credential-visible
  organization set, never any returned organization ID, name, handle, plan or payload;
- classify a proven organization mismatch as `CONFIGURED_ORG_ID_DRIFT`;
- if the configured organization matches but the exact configured project and its branch
  list remain denied, classify only
  `CONFIGURED_ORG_MATCH_EXACT_PROJECT_FORBIDDEN` rather than claiming an organization
  scope failure;
- keep the existing canonical-name project lookup gated behind successful direct
  organization read authority; do not broaden project enumeration for a limited key;
- malformed identity payloads remain `INVALID_PAYLOAD` / `UNRESOLVED` and never produce
  synthetic authority;
- never mutate Neon or Cloudflare from this diagnostic path.

## Blast radius and coupled consumers

The same failure-only diagnostic module is used by:

- `V10 Cloudflare Provider Readiness`;
- `V10 Cloudflare Candidate Deployment`;
- `V10 Cloudflare Production Release`.

The correction belongs in the shared diagnostic module and its deterministic regression
suite. No workflow ordering or provider-mutation command needs to change.

## What the corrected evidence can and cannot prove

The corrected diagnostic can prove whether the configured organization belongs to the
credential-visible organization set and can distinguish user-vs-organization API-key
authentication at the documented method level.

It still cannot infer the hidden project bound to a project-scoped key. Neon intentionally
limits project-scoped keys to one project, and unrelated projects are not a safe existence
oracle. If the configured organization matches while the exact project remains denied,
the remaining external boundary is a project/key binding or provider authorization
mismatch. The OWNER/provider action must be based on that narrowed evidence rather than
another speculative organization change.

## Permanent learning

- Credential identity and resource authorization are different evidence surfaces.
- A 403 on an organization resource is expected for a legitimate project-scoped key and
  must not be labeled as organization drift without an identity-level comparison.
- Provider-documented identity endpoints should be preferred over broad enumeration when
  diagnosing least-privilege credentials.
- Opaque authentication metadata (`account_id`, `auth_data`) is not needed for this
  classification and must not be logged.
- Diagnostic precision must increase without expanding mutation authority or weakening
  the release gate.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- broker write remains OFF.
- `trading_methods=false` remains unchanged.
- `REAL_TRADING_ENABLED=false` remains unchanged.
- No real credential, token, password, full provider identifier, database secret,
  connection URI or provider-private payload is recorded here or emitted by the probe.
- No Cloudflare or Neon mutation is authorized by this diagnostic correction alone.
