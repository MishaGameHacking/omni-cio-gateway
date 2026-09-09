# V10 Engineering Failure Learning Ledger — FL109

Date: 2026-09-09  
Scope: CF-D GitHub OIDC staging ingress authority channel  
Authority: Amendment 8 + Amendment 12 + Amendment 14 + Amendment 15 + Amendment 16

## Exact accepted precursor and new MAIN_RED_STOP evidence

PR #476 was squash-merged as protected `main`
`b378bdf2619ce57b5fde9311557b301d671b326f`. All eleven exact-main push workflows and
Regression Shield run `34394442874` completed successfully.

The automatically triggered exact-main `V10 Cloudflare Production Release` run
`34395566211` then proved the accepted staging Worker and serving Container at the exact same
source SHA, accepted staging database health, canonical domain configuration and production
Worker anchor. The one-time production database bootstrap stopped fail-closed with the newly
bounded code:

`CLOUDFLARE_CF_D_STAGING_HTTP_403_UNCLASSIFIED`

Production deployment and live production acceptance did not run. Cleanup/quarantine
completed.

## Root-cause class

`CF_D_PUBLIC_STANDARD_AUTHORIZATION_EDGE_NAMESPACE_COLLISION`

The same accepted staging Worker already accepts a source-controlled internal POST custody
operation through a dedicated application header, while the production bootstrap request is
the only release-authority request that presents the GitHub OIDC JWT in the public standard
`Authorization` channel. All source-controlled Worker, Container, hosted-security and CF-D
route `403` responses are bounded JSON classes and would have been classified by FL108.
Therefore the remaining unclassified `403` is outside those application response contracts and
is coupled to the public edge authentication namespace rather than to GitHub OIDC claim
validation inside the CF-D route.

Cloudflare documents that edge security and Access can reject requests before Worker code runs.
GitHub OIDC is Omni-CIO application authority, not Cloudflare edge authentication authority, so
sharing the public standard `Authorization` channel is an unnecessary provider-policy coupling.

## Corrective design

The external release runner now sends the ephemeral GitHub OIDC JWT only in the dedicated
`X-Omni-GitHub-OIDC` header together with the existing exact-source header. It does not send an
`Authorization` header to the public staging `workers.dev` ingress.

The trusted staging Worker owns the authority translation:

1. require exact POST path and exact source SHA;
2. reject any caller that also presents public `Authorization`;
3. require one bounded three-segment JWT-shaped OIDC value no larger than 16 KiB;
4. delete the dedicated ingress header;
5. materialize `Authorization: Bearer <OIDC>` only inside the Worker-to-Container request;
6. strip the dedicated OIDC header from every generic Worker-to-Container request as a
   defense-in-depth invariant.

The existing Container/FastAPI route remains the cryptographic authority. It still verifies the
GitHub OIDC signature/claims through the existing Neon Function flow, exact SHA, repository,
workflow, ref, event, runner, run ID/attempt and replay protections. No claim is trusted merely
because the Worker transported it.

## Security properties

- no long-lived credential is introduced;
- no GitHub OIDC token is logged or reflected;
- no Cloudflare Access/WAF/security control is disabled or bypassed;
- the public standard `Authorization` namespace is no longer overloaded by application OIDC;
- the custom OIDC header cannot reach generic product routes or the Container unchanged;
- existing exact-SHA and route/Function failure taxonomies remain unchanged;
- `PUBLIC_MULTI_USER_ENABLED=false`, `trading_methods=false` and
  `REAL_TRADING_ENABLED=false` remain protected.

## Permanent regression guards

Deterministic Node tests require trusted ingress to translate only an exact bounded OIDC request,
reject public Authorization, malformed/missing OIDC, path/method/SHA drift and never reflect the
token in an error. A Python runner test requires the public staging request to contain the
dedicated OIDC header, exact SHA and no `Authorization` header.

## Acceptance rule

This is a focused `MAIN_RED_STOP` repair. It requires exact-head full certification, Sonar and
independent review, zero blocking threads, squash merge, exact-new-main Regression Shield and a
fresh owning Cloudflare Production Release. If that release exposes a different bounded defect,
remain in `MAIN_RED_STOP` and repair only that next defect before unrelated work resumes.
