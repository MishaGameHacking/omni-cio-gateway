# Omni-CIO V10 — WP22A Provider Activation Boundary

Status: **PHASE B SOURCE-ONLY / PROVIDER MUTATION DISABLED**  
Owning package: **WP22A — External Web Access / OWNER Authentication Security Gate**

This document extends `V10_WP22A_EXECUTION_CONTRACT.md`. It does not mark WP22A complete and does not unlock WP23.

## 1. Purpose

Phase B needs a way to request reviewed provider work from accepted `main` without disclosing Cloudflare provider credentials, private provider state, tunnel credentials, or OWNER physical evidence to the ordinary persistent GitHub Actions runner.

The accepted trust split is:

`accepted main workflow -> short-lived GitHub OIDC request -> local protected controller -> later Cloudflare provider apply`

The ordinary `omni-cio-ci` runner may submit a signed request and read a sanitized result. It may not read or replace the protected controller, provider credential, private OpenTofu state, runtime tunnel token, or OWNER physical evidence.

GitHub engineering access is not provider-mutation authority. The privileged request contour is additionally bound to the stable GitHub account ID of the OWNER who owns the repository. A different collaborator may continue normal engineering through branches/PR/CI but cannot authorize this provider contour merely by having repository write access.

## 2. Why the provider token is not a normal Actions secret

The ordinary runner is a persistent self-hosted Windows execution surface and is treated as potentially compromised by the WP22A threat model. An Actions environment/secret controls when a value is injected, but it does not create a second OS trust boundary on the same runner.

Therefore:

- no Cloudflare API token is stored in a repository or workflow secret for this contour;
- no Cloudflare provider credential is injected into `omni-cio-ci`;
- no provider credential is accepted as `workflow_dispatch` input;
- no provider credential is written to Actions logs, artifacts, workspace, request queue, or result queue;
- later provider mutation executes only inside the protected local controller contour after a separate accepted source-only implementation adds the provider apply path.

## 3. Phase-B1 scope and hard stop

This source-only Phase-B1 increment implements only the authenticated request/controller boundary.

It MUST NOT:

- call Cloudflare APIs;
- run OpenTofu `plan`, `apply`, `destroy`, or state mutation;
- publish DNS;
- start Cloudflare Tunnel;
- retrieve or store a tunnel token;
- request a Cloudflare provider token from the OWNER;
- generate or attest OWNER physical evidence.

A successfully validated request returns the reason `WP22A_PROVIDER_BOUNDARY_READY_NO_MUTATION` and `mutation_performed=false`. Any other interpretation is a failure.

Provider apply/preflight/tunnel-token/rollback logic is a later source-only WP22A Phase-B increment and remains blocked until this boundary itself is accepted through PR CI, squash merge, exact `main` verification, and post-merge Regression Shield.

## 4. GitHub request workflow

`.github/workflows/v10-wp22a-provider-activation.yml` is deliberately:

- `workflow_dispatch` only;
- `main` only at runtime;
- exact checked-out `GITHUB_SHA` only;
- clean-worktree only;
- exact OWNER `github.actor_id` only;
- fresh-dispatch only: `github.run_attempt` must be exactly `1`;
- fail-closed when `github.triggering_actor` differs from the original `github.actor` as defense in depth;
- `contents: read` plus `id-token: write` only;
- free of `secrets.*` and provider configuration inputs;
- bound to the fixed OIDC audience `omni-cio-wp22a-provider-controller`.

The controller independently validates the signed OIDC `run_attempt=1` claim. This is the authoritative no-rerun boundary: GitHub re-runs may retain the privileges and signed identity of the original actor, so a privileged provider request must be started as a fresh OWNER dispatch rather than by re-running an older workflow run.

The workflow obtains a short-lived GitHub OIDC JWT using the runner-provided OIDC request variables, writes it only to a one-time local activation-request file, waits a bounded time for a sanitized controller result, then removes the request material. The ordinary runner does not receive delete authority on the sanitized result queue; result cleanup remains controller/SYSTEM-owned and is bounded to 24 hours.

The JWT is never printed.

## 5. Protected local controller

`install_wp22a_provider_controller.ps1` is invoked only from an exact, clean accepted `main` checkout. It does not copy the controller from the mutable worktree after validation. Instead, it reads the controller and activation-workflow text from the exact accepted Git commit object via `git --no-replace-objects ... cat-file blob`, with Git filesystem monitoring disabled for the handoff commands. Replacement refs therefore cannot substitute another object for the reviewed implementation SHA. The controller text is held in the elevated installer process, written into protected ProgramData, and read back for an exact copy comparison before the scheduled task is created.

Before it creates the protected contour, the installer resolves exactly one Actions runner service whose executable path belongs to the accepted `C:\actions-runner` root. It fails closed if that runner uses LocalSystem or is a direct member of the local Administrators group. This prevents privilege drift from silently turning the ordinary CI identity into an identity that inherits the Administrators full-control grant on the protected controller root.

Protected root:

`C:\ProgramData\OmniCIO\private\wp22a-provider-controller`

The root contains only controller/config/replay data in Phase-B1. SYSTEM and local Administrators have full control. The ordinary runner SID receives no allow ACE on that protected root and must remain non-administrator.

Exchange roots are separate:

- request queue: `C:\ProgramData\OmniCIO\runtime\wp22a-provider-requests`;
- sanitized result queue: `C:\ProgramData\OmniCIO\runtime\wp22a-provider-results`.

The request queue is untrusted input. Tampering cannot authorize provider work because authorization comes from the signed OIDC token and exact claims. The result queue is written and retention-managed by SYSTEM/controller and is read-only to the ordinary runner. It never contains credentials, private state, OWNER identity, or physical evidence. Controller cleanup removes only correctly named stale result/temp files older than 24 hours, so the exchange contour cannot grow without bound while the runner remains unable to rewrite or delete controller results.

## 6. OIDC validation contract

The controller validates all of the following before acknowledging a request:

- JWT `alg` is exactly `RS256`;
- signature validates against the current JWKS URI discovered from `https://token.actions.githubusercontent.com/.well-known/openid-configuration`;
- issuer is exactly `https://token.actions.githubusercontent.com`;
- audience contains exactly the reviewed controller audience for this request;
- `repository` is exactly `MishaGameHacking/omni-cio-gateway`;
- `repository_id` is exactly `1312247309`;
- `actor_id` is exactly the reviewed stable OWNER GitHub account ID;
- `ref` is exactly `refs/heads/main`;
- `event_name` is exactly `workflow_dispatch`;
- `workflow_ref` is exactly `MishaGameHacking/omni-cio-gateway/.github/workflows/v10-wp22a-provider-activation.yml@refs/heads/main`;
- `workflow_sha` equals the locally installed accepted implementation SHA;
- `runner_environment` is exactly `self-hosted`;
- JWT `run_id` equals request `run_id`;
- signed `run_attempt` is exactly `1`;
- request `implementation_sha` equals the locally installed accepted SHA;
- `exp`, `nbf`, and `iat` are inside the bounded clock-skew/age window;
- `jti` is non-empty and has not already been consumed.

A consumed `jti` is retained in the protected replay cache for a bounded period. Replay fails closed.

The stable numeric OWNER actor ID is identity metadata, not a secret or provider credential. Changing the OWNER GitHub identity requires a reviewed source change and a new accepted-main/post-merge evidence cycle before this privileged contour can be used again.

## 7. Future protected provider state

The later provider-apply increment must keep these paths inside the same protected trust contour, never the repository or Actions artifacts:

- DPAPI LocalMachine-encrypted Cloudflare API credential;
- private OpenTofu state and plan material;
- non-public account/zone/hostname/team configuration;
- provider verification details that are unsafe to expose to the runner.

When the later apply path exists, the Cloudflare API token must be decrypted only inside the controller process and passed transiently to a child provider process without command-line/log exposure.

The Cloudflare Tunnel run token must be fetched only after the reviewed tunnel exists, using the provider API token, and written directly into the protected Lenovo runtime token file. It must not enter OpenTofu state, GitHub, Actions logs/artifacts, or an interactive runner prompt.

## 8. Recovery and failure semantics

Phase-B1 performs no provider/runtime mutation, so its recovery action is removal of the local controller/request/result contour only.

Future provider mutation must preserve the WP22A execution contract:

1. reconstruct/verify accepted local Web first;
2. preflight zone/full-DNS/hostname/Universal SSL/Zero Trust/IdP before publication;
3. apply Access/Tunnel/ingress/proxied DNS from accepted source;
4. retrieve tunnel runtime token separately;
5. install/verify runner loopback denial and pinned cloudflared;
6. start external connector only after Access/certificate/catch-all deny are proven;
7. on any late failure, remove/disable external reachability and connector first, then restore accepted local Web.

There is no unauthenticated fallback.

## 9. Evidence boundary

Controller results are machine-generated operational evidence only. They may state request validation reason codes, exact implementation SHA, run ID, and `mutation_performed`.

They cannot state that the OWNER used a phone, saw a certificate, completed authentication, or successfully rehearsed logout/session rejection. Those facts require the separate physical OWNER evidence step defined by the WP22A execution contract.

## 10. Safety invariants

This boundary does not change:

- `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker write authority;
- V9 rollback protection.
