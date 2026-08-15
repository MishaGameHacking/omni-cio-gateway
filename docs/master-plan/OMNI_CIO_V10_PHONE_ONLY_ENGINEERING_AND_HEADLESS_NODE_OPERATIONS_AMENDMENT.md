# Omni-CIO V10 — Browser-Only Phone Engineering / Headless Personal Node Operations Amendment

Status: **OWNER-APPROVED DRAFT — requires PR/CI/merge before becoming accepted authority**

Date: 2026-08-15

## 1. Purpose

The OWNER's normal engineering and product-control workflow moves to a **phone browser only**. Native mobile applications are not required for the normal workflow. The first Lenovo remains a replaceable headless Personal Node / Windows self-hosted CI continuity machine until a later reviewed replacement-node cutover. This amendment does not create a second product, repository, Web App or competing runtime stack.

The permanent engineering objective is stronger than opening GitHub from a phone: **GitHub is the engineering source of truth and automation hub for development plus connected engineering services.** After bounded one-time account/provider bootstrap, ordinary code, test, review, CI, deployment and supported infrastructure operations must be driven from source-controlled GitHub workflows/APIs rather than recurring OWNER dashboard clicking or local PowerShell.

## 2. Primary OWNER browser surfaces

Normal OWNER interaction after the transition is:

1. ChatGPT website in the phone browser for engineering direction and GitHub-connected development orchestration;
2. GitHub website in the phone browser for repository/PR/Actions/review/account control;
3. GitHub Codespaces browser UI only as a fallback full development environment when direct terminal/editor work is genuinely useful;
4. Omni-CIO Web in the phone browser as the ordinary product and operational UI after the responsible external-access gate is accepted.

Native GitHub/Tailscale/remote-desktop applications are not part of the required OWNER workflow. Local Lenovo PowerShell and external provider dashboards are setup/recovery surfaces, not the normal development loop.

## 3. GitHub-auth-first external-service policy

For new engineering/operations services, prefer providers that support **Sign in with GitHub / GitHub OAuth** for OWNER account creation and login. Where the provider supports GitHub login, use the OWNER's GitHub identity rather than creating a separate routine password identity.

GitHub login to a provider does not automatically grant repository or machine authority. Provider permissions remain least-privilege and explicit.

If a required provider does not support GitHub login, engineering must first document why it is required and whether an equivalent GitHub-auth-capable/free/open-source service can satisfy the V10 contract.

After account bootstrap, recurring provider operations should use, in order:

1. short-lived workload/federated identity where supported;
2. narrowly scoped provider credential stored only in GitHub Actions/Environment secrets;
3. bounded deploy hook/token when no stronger machine identity is practical;
4. recurring manual dashboard operation only if the provider has no safe automation interface.

Secrets must never be committed, echoed to logs, copied into Codespaces or returned through chat.

## 4. GitHub-first autonomous engineering contract

The engineering agent is expected to perform directly through GitHub whenever supported:

- restore accepted authority and current code;
- create/update focused branches and repository files;
- create/update PRs and issue/review state;
- inspect exact-head diffs, checks, Actions jobs and logs;
- fix ordinary code/test/CI failures at root cause;
- maintain source-controlled deployment/infrastructure automation;
- progress the current authorized WP without OWNER hand-holding until a true OWNER-only boundary is reached.

OWNER is not the transport layer between services. Asking the OWNER to repeatedly copy source, press deploy buttons, inspect routine CI logs or run routine PowerShell is not the target operating model.

## 5. GitHub Actions as automation bus

Routine automation should converge on source-controlled GitHub Actions and reviewed provider APIs. Actions may coordinate only operations allowed by the owning V10 contract, including CI/security/release validation, supported deployment, dependency automation, bounded health verification and reviewed jobs on the least-privilege Windows self-hosted runner.

The Actions bus must not become a hidden Administrator shell. GitHub access does not imply broker, Real-money, secret-export, Windows Administrator, ruleset-bypass or arbitrary infrastructure authority.

## 6. Browser-only remote-access requirement

The final OWNER phone access path to Omni-CIO must work from a normal standards-compliant mobile browser **without requiring installation of a VPN/device client application**.

This requirement changes the candidate transport evaluation for WP22A but does not bypass its security Exit Gate.

Tailscale may still be useful for machine-to-machine/CI/private infrastructure, and it supports GitHub as an identity provider, but Tailscale's normal user-device tailnet access requires installing its device client. Therefore Tailscale Serve is no longer sufficient as the required OWNER phone access path under this browser-only amendment.

A clientless Zero-Trust reverse-proxy/tunnel design is now the preferred WP22A candidate. Cloudflare Access + Cloudflare Tunnel is the initial candidate because:

- Cloudflare account login supports GitHub social login;
- Cloudflare Access supports GitHub as an identity provider;
- private/self-hosted Web apps can be reached from a browser without a VPN/client application;
- Tunnel is outbound-only from the Personal Node and requires no public inbound port;
- Tunnel/Access configuration can be managed through API/Terraform, allowing GitHub-driven infrastructure-as-code after one-time bootstrap;
- a Free Zero Trust plan exists for small deployments, subject to exact feature/security/capacity verification before acceptance.

This is a candidate architecture, not automatic acceptance. WP22A must rework/review host/origin/session/proxy trust, anti-spoofing, identity, TLS, rollback, recovery and OWNER evidence for the selected clientless provider before any exposure is accepted.

## 7. Headless node contract

The Lenovo/new Personal Node must operate without an OWNER keeping a terminal open. Routine reboot recovery, service supervision, scheduled work, backup and normal Web operation must be automatic/fail-closed according to accepted V10 contracts.

Routine OWNER operations safe to expose remotely should be implemented through the existing Omni-CIO Web/System surface using typed, allowlisted, audited operations rather than arbitrary shell execution.

The Web control plane must not expose unrestricted PowerShell, filesystem mutation, SQL, GitHub bypass, secret export, broker credential disclosure, transfer/withdrawal authority or Real-money approval bypass.

The self-hosted GitHub runner remains non-admin/least-privilege.

## 8. One-time setup versus recurring OWNER work

Acceptable OWNER participation is deliberately front-loaded and rare:

- initial website sign-in/authorization to a provider, preferably through GitHub;
- creation/approval of a provider OAuth/federated identity or narrowly scoped API credential when GitHub cannot create it itself;
- storing a resulting secret once into the reviewed GitHub secret/environment boundary without exposing it to chat;
- physical/firmware/BitLocker/hardware action;
- an explicit OWNER decision or security/Real-money approval required by the Master Plan.

After bootstrap, provider operation returns to GitHub-driven automation.

## 9. Service/cost policy

Priority order:

1. already-paid GitHub Pro capabilities;
2. free/open-source/self-hosted capabilities compatible with V10;
3. free tiers that satisfy availability/security/recovery requirements;
4. paid service only after documented insufficiency of the earlier options and OWNER approval.

A free tier that sleeps, loses required durable state, weakens security/recovery or cannot meet capacity requirements cannot be treated as production-equivalent merely because it costs zero.

## 10. Render boundary

The accepted V9 `app:app` Render service remains the protected V9 production/recovery baseline until a responsible V10 parity/decommission gate replaces it. Render supports GitHub account login and GitHub deployment integration, so recurring manual deploy clicking should be avoided where the accepted deployment contract permits automation.

Phone-browser engineering does not move private V10 state or broker secrets into Render and does not turn Render into a competing V10 Personal Node.

## 11. WP22A interaction

WP22A remains the current functional package and is not renumbered or bypassed. Existing PR #317 remains unaccepted. Its Tailscale-specific implementation/evidence cannot be merged merely because earlier code passed tests: it must be reconciled with this browser-only OWNER requirement after this amendment itself is accepted.

The selected browser-only access path must preserve the single Omni-CIO Web App, server-side sessions, OWNER identity, loopback/private-origin protection, no broker-write expansion, no public unauthenticated ingress and explicit rollback/recovery evidence.

Any machine-bound evidence must be re-proven on the actual Personal Node used for final acceptance.

## 12. Physical/admin exception boundary

Browser-only means normal operation and engineering do not require local-console use. It cannot eliminate genuinely physical recovery operations such as failed hardware replacement, firmware/UEFI intervention, BitLocker recovery, initial trust bootstrap or another OS/admin action that cannot be safely delegated.

When unavoidable, the existing OWNER hand-off rule remains: one reviewed idempotent operation, Administrator only when necessary, PASS/FAIL evidence only, and no secrets in chat/GitHub.

## 13. Safety invariants

This amendment does not change:

- protected V9 `app:app` rollback;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker READ/Sandbox/Real credential separation;
- no transfer/withdrawal authority;
- PR + exact-head CI + squash merge discipline;
- GitHub as engineering source of truth;
- private durable state / GitHub source / runtime secrets separation.

## 14. Acceptance

This amendment becomes active only after its focused PR passes required checks, is squash-merged to `main`, and any required post-merge Regression Shield is GREEN.
