# Omni-CIO V10 — Browser-Only Phone Engineering Runbook

Status: **ACCEPTED** — browser-only/headless operating model accepted through PR #319; post-merge Regression Shield #1496 completed SUCCESS on exact `main` `9ad0eeb8d22895c3790fc5c7c78e9faf72a670e2`.

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

## OWNER instruction standard

Whenever OWNER action is genuinely required, engineering must provide instructions that are difficult to misinterpret on a phone browser.

Required format:

1. **Purpose** — one sentence explaining why the action is needed.
2. **Open** — exact website/service name and a direct HTTPS link when a stable official URL exists.
3. **Click path** — exact menu/button sequence using the current UI labels when verified.
4. **Do** — one bounded action at a time; do not mix optional and required actions.
5. **Expected result** — exact success state, text, status, or screen the OWNER should see.
6. **Stop condition** — what unexpected state means stop and send a screenshot/text instead of guessing.
7. **Do not do** — explicit warnings for destructive, paid, public-ingress, secret-disclosure, or authority-expanding actions.
8. **Return only** — the minimum safe result engineering needs back.

Additional rules:

- Prefer direct official links over "find this page yourself".
- Do not ask the OWNER to inspect ordinary logs, compare code, or troubleshoot routine CI.
- Do not ask the OWNER to perform multiple unrelated provider actions in one hand-off.
- If UI labels or provider behavior may have changed, verify current official documentation before giving click-by-click instructions.
- If a paid action is optional, label it optional and do not present it as required.
- If an action may incur charges, state the expected pricing model/cost boundary before the OWNER confirms it.

## Service-selection gate

Engineering must not select a service merely because it is popular, free, or already familiar. For every material external service, compare viable candidates against the actual Omni-CIO V10 requirements and document the reason for the chosen service.

Decision order:

1. **Requirement fit** — does it satisfy the owning WP/architecture contract without weakening safety or recovery?
2. **Security** — least privilege, strong identity, MFA/SSO, secret isolation, auditability, secure defaults, no unnecessary public ingress.
3. **GitHub automation** — GitHub login where appropriate; GitHub Actions/API/CLI/Terraform or equivalent machine interface; OIDC/federated identity preferred over long-lived credentials.
4. **Browser-only OWNER UX** — routine use must work from the phone browser without a required native app when this is part of the product requirement.
5. **Reliability/availability** — sleep/idle behavior, quotas, SLA/support, restart/recovery characteristics, regional/service dependencies.
6. **Durability/recovery** — backup/export/restore path, portability, provider-failure recovery, no hidden single point of failure.
7. **Privacy/data custody** — whether private portfolio, broker credentials, identity data, logs, or telemetry leave the Personal Node and whether that is actually authorized.
8. **Cost** — prefer already-paid GitHub Pro, OSS/self-hosted, and genuinely sufficient free tiers; move to paid only when measured requirements justify it.
9. **Lock-in/exit** — configuration portability, standard protocols, IaC support, exportability, replacement path.
10. **Operational burden** — ongoing OWNER clicks, manual renewals, credential rotation, dashboard dependence, maintenance load.
11. **Legal/broker/commercial constraints** — applicable data-processing, broker-terms, geographic, sanctions, licensing, or commercial restrictions.
12. **Performance/capacity** — latency, throughput, concurrency, storage and compute limits against expected V10 load.

A free tier is rejected for production use if its sleeping, durability, security, quota, recovery, or support limitations violate the owning V10 contract. A paid service may be recommended when it is materially safer, more reliable, more automatable, or operationally cheaper after total-cost analysis.

For a material choice, the OWNER-facing recommendation should contain only:

- **Recommended:** service/tier;
- **Why:** 3–5 decisive requirement-based reasons;
- **Cost now:** free/already-paid/estimated recurring cost;
- **Main limitation:** the most important tradeoff;
- **Fallback:** the next-best compatible alternative;
- **OWNER action:** only if one-time signup/consent/payment is actually required.

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
