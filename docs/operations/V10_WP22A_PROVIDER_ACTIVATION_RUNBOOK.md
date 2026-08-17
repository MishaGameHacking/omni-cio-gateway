# Omni-CIO V10 — WP22A Provider Activation Runbook

Status: **Phase-B1 source-only; no Cloudflare or Lenovo external-access mutation is authorized by this revision.**

## 1. Preconditions

Do not install or invoke the privileged contour from an open feature branch.

Before any OWNER/admin installation action, engineering must have already proved:

1. the Phase-B1 source PR is squash-merged;
2. the exact new `main` SHA is known;
3. the post-merge Regression Shield for that exact SHA is GREEN;
4. no blocking review thread remains;
5. `WP23` remains locked;
6. `trading_methods=false` and `REAL_TRADING_ENABLED=false` remain unchanged.

Until all six are true, this runbook is documentation only and OWNER action is **NOT REQUIRED**.

## 2. What Phase-B1 installs

The installer creates a protected local request validator, not a Cloudflare deployment engine.

It installs:

- a reviewed controller body read from the exact accepted Git commit object rather than copied from mutable worktree bytes;
- a protected controller configuration bound to one accepted implementation SHA and repository ID;
- a protected replay cache;
- an untrusted request queue;
- a sanitized result queue that is read-only to the ordinary runner and retention-managed by SYSTEM;
- a LocalSystem scheduled task that validates queued requests and removes correctly named stale result/temp files after 24 hours.

The Git handoff uses replacement refs disabled and filesystem monitoring disabled. The installed controller is read back and compared with the reviewed in-memory commit-object text before task registration.

It does not request, store, or use a Cloudflare token. It does not run OpenTofu. It does not start `cloudflared` or publish DNS.

## 3. Deterministic CI validation

PR CI may run:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass `
  -File infrastructure\windows\install_wp22a_provider_controller.ps1 `
  -ExpectedImplementationSha $env:GITHUB_SHA `
  -ValidateOnly -AsJson
```

`-ValidateOnly` must not require Administrator rights and must not modify ProgramData, Scheduled Tasks, Cloudflare, DNS, or runtime state. It validates the controller/workflow source from the exact reviewed commit object for the supplied SHA.

The controller also exposes a source validation mode:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass `
  -File infrastructure\windows\run_wp22a_provider_controller.ps1 `
  -ValidateOnly -AsJson
```

This mode verifies constants/parser/runtime assumptions only. It does not fetch OIDC metadata or process requests.

## 4. Future OWNER/admin installation handoff

Only after the Phase-B1 PR and its post-merge Regression Shield are accepted may engineering ask the OWNER to perform the one-time Administrator installation. The exact command must be generated from the then-current accepted `main` SHA, not copied from this document with a stale SHA.

The installer requires:

- Administrator PowerShell;
- repository checkout on branch `main`;
- exact `HEAD == ExpectedImplementationSha`;
- clean worktree;
- reviewed controller/workflow blobs available from that exact commit with Git replacement refs disabled;
- exactly one ordinary GitHub Actions runner service whose executable path belongs to `C:\actions-runner`;
- runner identity is not LocalSystem;
- runner identity is not a direct member of the local Administrators group.

If source provenance or runner privilege drift violates any condition, installation fails closed. Do not weaken the Git handoff, ACL/controller design, or runner identity to work around the failure.

No Cloudflare credential is entered during Phase-B1 installation.

## 5. Activation request workflow

The source-controlled workflow is manual-dispatch only. It must reject execution unless:

- `github.ref == refs/heads/main`;
- the checked-out `HEAD` equals `github.sha`;
- the worktree is clean;
- `github.actor_id` equals the reviewed stable OWNER GitHub account ID;
- `github.run_attempt == 1`;
- `github.triggering_actor == github.actor` as an additional workflow-side guard.

A privileged provider-boundary run is never re-run. If a run fails, investigate the failure and start a new OWNER `workflow_dispatch` only after the cause is understood. The protected controller independently requires signed OIDC `run_attempt=1`, so a runner-side bypass of the workflow guard cannot turn an older OWNER run into fresh provider authority. This matters because GitHub re-runs retain the original run actor's privileges.

The stable numeric OWNER account ID is identity metadata, not a provider secret. If the OWNER GitHub identity changes, engineering must update the reviewed source and repeat the exact-head/merge/post-merge acceptance cycle before this contour can be used again.

The job requests a GitHub OIDC token for audience:

`omni-cio-wp22a-provider-controller`

It writes a one-time request into the local request queue and waits for a result bearing the same random request ID. The runner removes only its request material. It does not receive result-delete authority; sanitized result retention is controlled by the LocalSystem controller and bounded to 24 hours.

Expected successful Phase-B1 result:

- `accepted=true`;
- `mutation_performed=false`;
- `reason=WP22A_PROVIDER_BOUNDARY_READY_NO_MUTATION`;
- exact installed implementation SHA;
- exact GitHub run ID.

Anything else is a failure.

## 6. OIDC failure handling

The controller rejects and sanitizes failures. Examples include:

- signature/JWKS failure;
- wrong issuer/audience;
- wrong repository or repository ID;
- wrong OWNER `actor_id`;
- signed `run_attempt` other than `1`;
- non-main ref;
- non-`workflow_dispatch` event;
- wrong workflow ref;
- stale/wrong workflow SHA;
- non-self-hosted runner claim;
- expired/not-yet-valid/too-old token;
- request/token run-ID mismatch;
- repeated `jti`.

No failure path falls back to unsigned request fields.

## 7. Queue and controller recovery

The request queue is untrusted input. The sanitized result queue is not an authority source and contains only bounded machine-generated status fields. The ordinary runner may read results but cannot rewrite or delete them; SYSTEM owns result cleanup. Correctly named `.json`/`.tmp` result files older than 24 hours are removed by the controller so the exchange state is bounded.

If the Phase-B1 local boundary must be removed, use the installer cleanup mode only from the exact accepted source that owns the installation:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass `
  -File infrastructure\windows\install_wp22a_provider_controller.ps1 `
  -ExpectedImplementationSha <EXACT_ACCEPTED_MAIN_SHA> `
  -Cleanup -AsJson
```

Cleanup removes the LocalSystem task and the Phase-B1 controller/request/result roots. It does not touch accepted WP15 local Web, broker secrets, PostgreSQL durable state, or V9 rollback.

## 8. Provider apply is intentionally still blocked

The next source-only Phase-B increment must add and test, before any real credential exists on the node:

- provider preflight of active/full zone and first-level hostname;
- active Universal SSL exact-host coverage and managed-renewal proof;
- exact Zero Trust organization and restricted Cloudflare account-member IdP proof;
- protected private OpenTofu state;
- provider plan/apply/reconcile/rollback controller logic;
- provider API retrieval of the tunnel runtime token outside OpenTofu state;
- refactor of the dormant Lenovo clientless provisioner so it consumes only the controller-prepared protected runtime token and has no manual tunnel-token prompt;
- independent provider/Lenovo verification and reachability-first rollback.

Until that increment is itself merged and post-merge Regression Shield is GREEN, a Phase-B1 activation request can only prove the trust boundary is ready. It cannot publish Omni-CIO.

## 9. Physical OWNER acceptance remains separate

No controller/workflow output is physical OWNER evidence. Phone-browser TLS, Access authentication, Omni-CIO remote session behavior, logout, and stale-session rejection remain a later OWNER physical rehearsal after provider/runtime activation has independently passed.
