# Omni-CIO V10 — Browser-Only Phone Engineering Runbook

Status: **DRAFT with phone-only engineering amendment**

## Goal

The OWNER directs development and uses Omni-CIO from a phone **through websites in the browser only** while the Windows Personal Node runs headless. Local node PowerShell and provider dashboards are reserved for initial setup, genuine physical/admin recovery or another explicit OWNER-only boundary.

The normal engineering loop is:

`ChatGPT Web -> GitHub Web -> source-controlled Actions/provider APIs -> CI/deployment/runtime verification`.

Repeated OWNER clicking is not part of the target operating model.

## Required phone websites

- ChatGPT website — engineering direction/orchestration.
- GitHub website — repository, PR, Actions, review and account control.
- GitHub Codespaces website — fallback browser IDE/terminal only when direct interactive work is genuinely useful.
- Omni-CIO Web — ordinary product/operations UI after the responsible external-access gate is accepted.

No native mobile application is required for normal OWNER operation.

## External-service account rule

When a new service supports **Sign in with GitHub**, use it. Prefer not to create another routine password identity.

After the one-time website authorization/bootstrap, normal provider operations should return to GitHub Actions/API/IaC rather than requiring recurring OWNER dashboard work.

Never paste provider secrets into chat. If a provider credential is genuinely needed, create the narrowest credential and store it once in the reviewed GitHub Actions/Environment secret boundary.

## Autonomous daily development flow

1. OWNER states the goal in ChatGPT Web.
2. Engineering restores GitHub source of truth and works only in the current authorized branch/WP.
3. Engineering changes repository files directly through GitHub-connected tooling; OWNER does not move source files between services.
4. Changes go to a focused branch/PR, never directly to `main`.
5. GitHub Actions runs source-controlled tests/security/deployment orchestration. Windows/self-hosted exact-head gates run on the headless Personal Node where required.
6. Engineering reads ordinary CI logs and fixes ordinary code/test/CI failures autonomously.
7. Connected providers are controlled through reviewed GitHub integrations/APIs/CLI/Terraform whenever available.
8. OWNER receives only concise PASS/FAIL/blocker status and is contacted only for a true OWNER-only action.
9. Merge occurs only after exact-head/threads/squash discipline is satisfied.

## Browser-only external access

A phone-browser-only workflow means the final Omni-CIO access path must not require installing a VPN/device client on the phone.

Tailscale supports GitHub identity and remains useful for some machine/CI cases, but normal tailnet access from a user phone requires a Tailscale client. Therefore it is no longer the required OWNER phone transport.

The initial WP22A clientless candidate is **Cloudflare Access + Cloudflare Tunnel** because official Cloudflare capabilities support:

- Cloudflare account sign-in through GitHub social login;
- GitHub as an Access identity provider;
- browser access to self-hosted/private Web apps without a VPN/client application;
- outbound-only tunnel from the Personal Node, with no public inbound origin port;
- API/Terraform management for GitHub-driven infrastructure-as-code;
- a Free Zero Trust plan suitable for initial small deployments, subject to exact acceptance review.

Do not treat this runbook as WP22A acceptance. The existing Tailscale-specific PR #317 must be reconciled/reworked only after this amendment is accepted.

## Provider examples

### Render

Use Render's GitHub login/integration and reviewed GitHub-driven deployment where the existing V9 deployment contract permits it. Avoid recurring manual deploy buttons. API keys/deploy hooks are secrets.

### Cloudflare candidate

Initial OWNER account bootstrap should use Cloudflare website **Sign in with GitHub**. Do not create Tunnel/Access/API credentials until engineering has source-controlled the exact WP22A design and minimum permissions.

Once accepted, manage repeatable Cloudflare resources through reviewed Terraform/API from GitHub; dashboard work becomes setup/recovery only.

### Headless Windows node

The self-hosted runner is an authoritative Windows execution surface only within reviewed least-privilege workflows. It is not an unrestricted remote Administrator shell.

## Codespaces boundary

Codespaces is optional engineering clean-room/fallback. It must not contain:

- broker READ/TRADE tokens;
- Telegram/VK production credentials;
- Cloudflare/Tailscale runtime secrets unless an owning contract explicitly establishes an isolated ephemeral CI credential path;
- BitLocker keys;
- DPAPI/runtime secret-store material;
- private portfolio/report payloads;
- Real-money confirmation/authority.

## When engineering may interrupt the OWNER

Routine code, formatting, tests, CI debugging, PR housekeeping, dependency updates and supported provider automation are engineering work.

OWNER involvement is reserved for:

- initial external-account website consent/credential bootstrap that no safe API can perform;
- entering a secret once into an approved protected boundary;
- physical hardware/BitLocker/UEFI action;
- Windows Administrator action that cannot safely be delegated;
- an irreversible/materially risky decision reserved to OWNER;
- required security/Real-money confirmation.

## Safety invariants

Browser-only operation never authorizes bypassing exact-head CI, protected `main`, Windows-specific acceptance, OWNER physical evidence, V9 `app:app` rollback, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, or broker/transfer/withdrawal prohibitions.
