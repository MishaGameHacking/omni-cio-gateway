# V10 Engineering Failure Learning Ledger — FL091

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, CF-D exact-main
production database bootstrap after accepted main
`2491ad5fb95321970d63e41ae36d3c30d04dbb3c`.

Owning recovery thread: `#430`.
Focused recovery PR: `#450`.

This correction does not authorize public multi-user activation, Telegram/VK provider
activation, broker write, Real execution or any new Work Package.

## Failure evidence

Exact-main production release run `33956589149` reached the production database
bootstrap boundary twice while preserving fail-closed release sequencing.

The fresh second attempt completed the exact-main post-merge gate, Cloudflare provider
and Workers Builds authority checks, pinned delivery/control-plane toolchain, Containers
registry authority, isolated staging Worker + Container deployment, staging release/health
acceptance, canonical public-domain configuration validation and production Worker anchor
reuse before stopping at the one-time production database bootstrap boundary.

Production had no accepted runtime database binding, so the OIDC bootstrap path was
required. The runner stopped at `CLOUDFLARE_CF_D_STAGING_BOOTSTRAP_FAILED`; production
promotion, Custom Domain and live acceptance remained skipped, and cleanup/quarantine
succeeded.

The source-controlled Neon Function was independently compared with the active provider
deployment. Provider drift was found and the exact accepted Function source was redeployed
through the connected Neon control plane without handling or exposing a provider secret.
A new release attempt still failed at the same boundary. Neon Function telemetry for that
failure window contained no invocation, localizing the immediate failure before Function
execution to staging Container -> Neon Function transport.

## Initial root cause class

`CF_D_CONTAINER_DIRECT_NEON_FUNCTION_EGRESS_COUPLING`

The staging bootstrap proxy performed a direct public HTTPS request from the backend
Container to a runtime-derived Neon Function origin. Ordinary staging health did not
exercise that egress path, and deterministic tests replaced `httpx.Client` with an
in-process double. Exact-main staging health could therefore be GREEN while the only
first-production-bootstrap egress path remained unproved.

This is not solved by requesting another long-lived secret, reintroducing Neon management
API authority, hardcoding project/branch identifiers, weakening OIDC validation, widening
network access or treating a transport failure as success.

## First bridge correction and review learning

The first PR #450 correction moved the failed public egress through Cloudflare Containers
`outboundByHost`: the staging backend called one fixed same-machine virtual hostname and
the Worker upgraded that call to HTTPS. Independent Files-changed review correctly found
that the first regression only searched source strings, so the egress policy was extracted
into `cloudflare/src/cf-d-neon-bootstrap-egress.js` and executable Node positive/negative
tests were added to the normal product Web test command.

The executable-policy review rule is retained: a material egress allowlist or authority
policy requires behavioral positive/negative tests in addition to source/governance
guards.

## Exact-head security-analysis evidence

Fresh verification head `61deb599c5fd7f68ca9c116e351476dd2efec833` completed the
repository-owned gates, but SonarQube Cloud reported **Security Rating on New Code = B**
where A is required and exposed two annotations through the check summary. The available
connector does not expose the private issue payload, so this ledger does not invent their
text.

A first coherent security-hygiene correction removed fixed synthetic Bearer and DSN
credential material from the new tests. Head
`86cb38f0846943b91321925fe92a669df7a0b9ed` then completed all 13 repository GitHub
Actions workflows `success`, while SonarQube Cloud still reported the same Security Rating
B with two annotations. That disproves fixed synthetic credential material as the complete
root cause.

The remaining new-code architecture also exposed a real authority defect independent of
the unavailable annotation text: the Container supplied a target header that could choose
any URL matching the broad Frankfurt `cfdprodbootstrap` branch pattern. A compromised
Container could therefore choose a different same-pattern Neon branch. Strict hostname
syntax reduced SSRF surface but did not make the Container an appropriate provider
selection authority.

Sonar's JavaScript rule family classifies server-side request-forgery flows as
Vulnerabilities. The exact annotation payload remains unavailable, so the correction is
based on both the observable Security Rating evidence and the concrete cross-branch
provider-authority weakness rather than on an invented scanner message.

## Final root cause class

`CF_D_CONTAINER_CONTROLLED_PROVIDER_DESTINATION_AUTHORITY`

The staging Container is allowed to request one bootstrap operation, but it must not
select the external provider destination. Provider routing is a trusted Worker/platform
responsibility. The target must be bound to the same staging PostgreSQL branch that is
already accepted as the runtime data authority.

## Coherent authority correction

The complete failing block is now hardened end-to-end:

1. `apps/api/cf_d_database_bootstrap.py` sends only the bounded OIDC assertion and exact
   release SHA to `http://cf-d-neon-bootstrap.internal/`. It no longer sends a provider
   target header and no longer queries PostgreSQL to choose an external destination.
2. `Backend.outboundByHost` runs in the trusted Workers runtime and receives the Worker
   bindings independently of the Container sandbox.
3. The Worker accepts only the exact virtual HTTP hostname/root path, `POST`, bounded
   Bearer shape, exact one-field JSON body, and exact current `SOURCE_SHA`. Any legacy
   target-selection header is rejected.
4. The Worker validates its own existing `OMNI_V10_POSTGRES_DSN` binding as the staging
   role on a Frankfurt Neon endpoint with mandatory TLS connection parameters. No new
   secret or management-plane authority is introduced.
5. Using that already-required runtime database binding, the Worker performs the same
   Neon SQL-over-HTTP protocol already used by the accepted source-controlled Function to
   read `current_setting('neon.branch_id', true)`. The SQL endpoint is derived only from
   the validated Worker runtime binding, never from the Container request.
6. The returned branch ID is strictly validated, combined with the validated database
   cell, and used to construct exactly that branch's `cfdprodbootstrap` HTTPS Function
   origin. The Container cannot choose a branch, project, region, path, port or hostname.
7. The Worker reconstructs the outbound provider request with only Authorization,
   Accept, Content-Type and the exact source SHA body. Container-supplied Host, target or
   arbitrary headers are not forwarded.
8. Node behavioral tests execute the real policy and prove trusted branch resolution,
   target-header rejection, route/method/SHA negatives, staging-role/Frankfurt/TLS DSN
   negatives, and failed/malformed branch metadata fail-closed behavior.
9. Python integration tests prove the staging FastAPI producer has no provider destination
   authority and cannot query branch metadata while constructing the virtual request.
10. Existing product internet policy is not globally disabled or widened. The change
    supplies only the dedicated bootstrap bridge and retains existing product traffic.

## Why this closes the defect class rather than silencing the analyzer

The correction removes request-controlled provider selection instead of adding a Sonar
suppression, excluding files, weakening the Quality Gate or teaching the scanner a magic
allowlist comment. The external destination is derived from an already-required trusted
Worker database binding plus authenticated database branch metadata. This is also a real
least-authority improvement if the backend Container is compromised.

No `NEON_API_KEY`, `NEON_PROJECT_ID`, `NEON_ORG_ID`, fixed provider branch ID, committed
DSN or provider credential is added. Neon management-plane authority remains absent from
the bootstrap path.

The new exact head requires a fresh complete verification cycle. If Sonar remains below
A, the remaining annotation set must be treated as a new evidence-backed defect class;
it must not be hidden by suppression or assumed to be equivalent to this correction.

## Blast radius and adjacent failure modes

Directly coupled surfaces reviewed:

- staging-only CF-D bootstrap route;
- Cloudflare Worker -> Container request restoration;
- Container outbound virtual-host boundary;
- Worker runtime PostgreSQL binding;
- Neon SQL-over-HTTP branch metadata lookup;
- short-lived GitHub OIDC forwarding;
- source-controlled Neon Function verifier/database role convergence;
- production secret bootstrap/reuse gate;
- existing staging and production Worker anchors;
- product Web Node test wiring;
- exact-main production release ordering and rollback boundary.

Adjacent modes addressed or preserved:

- Container-selected arbitrary URL/port/path/query/branch routing is eliminated;
- legacy target-selection input is rejected rather than ignored;
- the Worker database binding must be staging-role, Frankfurt and TLS-required;
- branch metadata must have one strict Neon branch ID and a valid DNS label size;
- outbound Function request headers are reconstructed from a small allowlist;
- provider response size remains bounded in the staging proxy;
- redirects and environment proxy inheritance remain disabled at the Container boundary;
- malformed/failed database metadata or provider responses remain fail-closed;
- production mutation remains impossible before bootstrap success;
- public multi-user and broker/Real authority remain unchanged.

## Permanent prevention rules

For future Container/provider integrations:

- a mocked HTTP client is insufficient evidence for provider-specific outbound routing;
- a Container must not select an external privileged provider destination merely because
  a URL passes syntax/hostname validation;
- when an outbound Worker has an existing trusted binding that can derive the exact
  provider resource, derive authority from that binding rather than from request input;
- material egress policy requires executable positive and negative tests;
- synthetic authentication/database credentials whose exact bytes are irrelevant are
  generated at test runtime rather than embedded as reusable literals;
- analyzer RED is evidence to diagnose, never a reason to suppress a rule or weaken a
  merge gate.

## Protected invariants

- protected V9 `app:app` is unchanged;
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged;
- Telegram/VK public activation remains outside this correction;
- broker write remains OFF;
- `trading_methods=false` remains unchanged;
- `REAL_TRADING_ENABLED=false` remains unchanged;
- no transfer/withdrawal/margin/leverage/uncovered-short authority is introduced;
- no provider token, database credential, OIDC assertion or private tenant payload is
  committed or logged;
- CF-D production promotion remains gated by exact-main SUCCESS-only evidence.
