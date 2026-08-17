# V10 WP22A provider Phase B runbook

Status: **SOURCE-CONTROLLED PHASE B PROCEDURE — WP22A REMAINS IN PROGRESS**

This runbook governs the first real Cloudflare provider mutation for the accepted
WP22A clientless browser-only architecture. It does not authorize WP23, public
registration, a second Web runtime, Render hosting, broker write authority, or
synthetic OWNER acceptance.

## 1. Safety boundary

The only provider resources owned by this procedure are:

- one remotely managed Cloudflare Tunnel named `omni-cio-v10-owner-web`;
- one OWNER-only Cloudflare Access policy;
- one self-hosted Cloudflare Access application;
- one tunnel configuration whose only application origin is `http://127.0.0.1:8765`
  and whose final ingress rule is `http_status:404`;
- one proxied first-level CNAME for the reviewed OWNER hostname.

The existing Cloudflare Zero Trust organization and the existing Cloudflare
identity provider restricted to Cloudflare account members are read-only
prerequisites. Phase B must not create a second Zero Trust organization or a
second identity provider.

`trading_methods=false`, `REAL_TRADING_ENABLED=false`, `app:app`, V9 rollback,
and the current broker authority remain unchanged.

## 2. Protected GitHub environment

Real Cloudflare provider credentials are allowed only after this source is
accepted on `main` and only in the GitHub Environment:

`wp22a-provider-production`

Before any provider secret is stored there, the environment must be configured
with a **custom deployment branch policy** containing exactly one branch rule:

`main`

No wildcard, tag rule, release branch, feature branch or pull-request head is
allowed. The workflow independently re-reads the environment policy through the
GitHub API, re-reads the current `main` SHA, compares it with the explicitly
entered accepted SHA, checks out that exact SHA, and fails closed before the
provider-secret step if any condition differs.

The provider workflow is `workflow_dispatch` only. It has no `push` or
`pull_request` mutation route, and its concurrency group is non-cancelling so a
provider apply/destroy cannot be interrupted by a newer dispatch.

## 3. Cloudflare API token scope

Use one narrowly scoped Cloudflare API token. Never use the Global API Key.
Restrict its Account resources to the exact OWNER account and its Zone resources
to the exact reviewed zone.

The token needs only the permissions required by the reviewed Terraform and
preflight/verification code:

- Account — **Cloudflare Tunnel Edit**;
- Account — **Access: Apps and Policies Edit**;
- Account — **Access: Organizations Read**;
- Account — **Access: Identity Providers Read**;
- Zone — **DNS Edit**;
- Zone — **Zone Read**;
- Zone — **SSL and Certificates Read**.

If the Cloudflare UI exposes the combined read permission
`Access: Organizations, Identity Providers, and Groups Read`, it may replace the
two separate Access read permissions above. Do not add Billing, Workers, WAF,
Zone Edit, Access Organizations Edit, Identity Providers Edit, API Tokens Edit,
or any unrelated permission merely to make a command pass.

Cloudflare documents that Edit permission is the write-capable CRUD level for a
permission group, that resources can be restricted to a specific account/zone,
and that a remotely managed tunnel token is a separate bearer secret. The tunnel
runtime token therefore remains outside Terraform state and outside GitHub
artifacts.

## 4. Protected environment secrets

The environment contains exactly these WP22A provider inputs:

- `WP22A_CLOUDFLARE_API_TOKEN`;
- `WP22A_CLOUDFLARE_ACCOUNT_ID`;
- `WP22A_CLOUDFLARE_ZONE_ID`;
- `WP22A_EXTERNAL_HOST`;
- `WP22A_CLOUDFLARE_TEAM_NAME`.

Do not put their real values in repository files, PR comments, issue comments,
workflow inputs, CI logs, uploaded artifacts or chat.

The hostname must be a first-level hostname of the active full-DNS zone because
WP22A deliberately relies on the normal Universal SSL wildcard coverage model.
The preflight verifies active/full DNS, zone/account binding, Universal SSL
`enabled=true`, an active universal certificate covering the exact hostname,
the exact Zero Trust auth domain, `allow_authenticate_via_warp=false`,
`deny_unmatched_requests=true`, and exactly one Cloudflare identity provider
restricted to account members.

## 5. Provider state discipline

OpenTofu is pinned to `1.12.5`. The Cloudflare provider is pinned to `5.22.0`
and installed only from the reviewed SHA-256-authenticated Windows package and
filesystem mirror.

Provider state is private local durable metadata under the protected runner
profile, never a repository file or artifact. Saved plans, plan JSON, state JSON
and raw OpenTofu logs exist only under `RUNNER_TEMP` and are deleted in `finally`.
They must never be printed or uploaded because OpenTofu saved plans/state can
contain sensitive values even when terminal output redacts them.

The local state file is treated as **untrusted durable metadata**, because the
same self-hosted runner also executes PR CI. Every protected provider operation
therefore:

1. structurally validates state against an exact resource-address allowlist;
2. rejects secret-like values in state;
3. reads the real provider resources through the protected API token;
4. binds the local state IDs to the exact live tunnel, Access application,
   Access policy and DNS record;
5. rejects a missing state if expected WP22A live resources already exist;
6. rejects apply plans containing delete/replace or unknown resources;
7. rejects destroy plans containing anything except delete/no-op for the exact
   WP22A resources.

A deleted, corrupted, poisoned or ambiguous state therefore causes a fail-closed
recovery condition rather than takeover of an unrelated Cloudflare resource.

## 6. Operation sequence

The protected workflow supports these explicit operations:

`preflight → plan → apply → verify → verify-live`

Use the exact accepted current `main` SHA for every dispatch.

### preflight

Read-only. Proves account/zone/certificate/Zero Trust/IdP prerequisites without
publishing a route.

### plan

Read-only against provider state. The saved plan is inspected locally as JSON
and discarded. No raw plan is uploaded or printed.

### apply

Requires the exact confirmation string:

`APPLY_WP22A_PROVIDER`

The already-guarded saved plan is applied. The resulting local state is again
validated and bound to the exact live provider resources. The post-apply live
verification intentionally does **not** require the tunnel to be Healthy yet;
local `cloudflared` has not been provisioned at this point.

### verify

Read-only provider/state verification after apply.

### verify-live

Read-only provider/state verification plus `tunnel status = healthy`. Run this
only after the protected Lenovo `cloudflared` runtime is actually connected.

## 7. Rollback

Provider rollback is external-route first. Use:

`destroy-plan → destroy`

`destroy` requires the exact confirmation string:

`DESTROY_WP22A_PROVIDER`

The state must still validate and bind to the exact live WP22A resources before
destruction. After the guarded destroy, the workflow independently verifies that
the expected tunnel, Access application and DNS record are absent, then removes
the local state/backup.

If state is missing or cannot be bound to the exact live resources, **do not
force-delete by guessed IDs**. Stop in recovery mode and reconcile the provider
state before attempting another mutation.

## 8. Tunnel runtime token

The remotely managed tunnel token is not a Terraform variable, resource field,
output, state value, artifact or repository secret. It is retrieved only after
the provider resources are accepted and is transferred into the protected
Lenovo runtime token file through the separate OWNER/admin local-runtime gate.
The GitHub CI runner must remain unable to read that final token file.

The current source-only Phase B provider work does not synthesize that physical
OWNER/admin evidence and does not make WP22A complete.

## 9. Acceptance remains separate

After provider apply and local runtime provisioning, WP22A still requires:

- exact-head provider verification;
- exact-head Lenovo verification and runner loopback denial;
- real phone-browser HTTPS reachability without a VPN/client app;
- real Cloudflare account-member identity authentication;
- inner exact OWNER binding;
- secure session/cookie/CSRF behavior;
- logout/server-side session revocation;
- all inherited Web pages remaining usable and read-safe;
- final sanitized OWNER evidence and the WP22A Exit Gate.

Until those checks are completed and the accepted status is merged after a GREEN
post-merge Regression Shield, **WP23 remains LOCKED**.
