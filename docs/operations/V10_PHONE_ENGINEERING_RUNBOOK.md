# Omni-CIO V10 — Phone Engineering Runbook

Status: **DRAFT with phone-only engineering amendment**

## Goal

The OWNER can direct development, inspect summarized PR/CI state and perform ordinary repository control from a phone while the Windows Personal Node runs headless. Local node PowerShell and provider dashboards are reserved for initial setup, genuine physical/admin recovery or another explicit OWNER-only boundary.

The normal engineering loop is **ChatGPT -> GitHub -> source-controlled Actions/provider APIs -> CI/deployment/runtime verification**. Repeated OWNER clicking is not part of the target operating model.

## Phone toolset

### Required

- ChatGPT mobile — engineering direction/orchestration.
- GitHub Mobile — notifications, PR/issues/reviews and quick repository control.
- Mobile browser signed in to GitHub — full repository/Actions/Codespaces access.

### Recommended fallback full IDE

GitHub Codespaces opened in the mobile browser. It provides browser VS Code, terminal, Git and application run/debug capability. Treat it as a disposable engineering environment; never provision production secrets into it.

### Product/private access

Tailscale mobile becomes the private transport for the WP22A phone rehearsal and, after acceptance, ordinary private phone access to the single Omni-CIO Web App. Tailscale configuration is not part of this amendment's acceptance and must still pass WP22A.

## Autonomous daily development flow

1. OWNER states the goal in ChatGPT mobile.
2. Engineering restores GitHub source of truth and works only in the current authorized branch/WP.
3. Engineering changes repository files directly through GitHub-connected tooling; OWNER does not copy/paste source files between systems.
4. Changes go to a focused GitHub branch/PR, never directly to `main`.
5. GitHub Actions runs source-controlled tests/security/deployment orchestration. Windows/self-hosted exact-head gates run on the headless Personal Node where required.
6. Engineering reads ordinary CI logs and fixes ordinary code/test/CI failures autonomously.
7. Connected providers are controlled through their reviewed GitHub integration/API/CLI whenever available; recurring manual dashboard deploy/configuration is not the default.
8. OWNER receives a concise PASS/FAIL/blocker summary on the phone and is contacted only when the contract requires a true OWNER action.
9. Merge occurs only after the existing exact-head/threads/squash discipline is satisfied.
10. Render behavior remains governed by the existing V9 deployment contract until a responsible V10 cutover replaces it.

## One-time service bootstrap pattern

For a new external service, engineering first determines whether GitHub can authenticate with a short-lived/federated identity. If not, use the narrowest supported service credential. OWNER interaction may be required once to create/authorize that identity/credential and place it into the reviewed GitHub Actions/Environment secret boundary.

After bootstrap, normal operation must be machine-driven from GitHub whenever the service offers a safe API/Git integration. Secrets are never committed, printed in Actions logs, copied to Codespaces or sent through ChatGPT.

Preferred order:

1. workload/federated identity;
2. narrowly scoped GitHub Actions/Environment credential;
3. bounded provider deploy hook/token;
4. manual provider UI only when no reviewed automation interface exists.

## External-service examples

### Render

Keep the accepted V9 `app:app` deployment boundary. Where the owning deployment contract permits it, use Render's GitHub integration or protected API/deploy-hook automation rather than recurring OWNER deploy clicks. A Render API key/deploy-hook URL is a secret.

### Tailscale

WP22A remains the authority. If GitHub-to-tailnet automation is accepted there, prefer Tailscale's supported GitHub integration using federated/workload identity or narrow OAuth scope instead of a long-lived reusable auth key. This does not authorize Funnel/public ingress.

### Headless Windows node

The self-hosted runner is an authoritative Windows execution surface only within its reviewed least-privilege workflows. It is not an unrestricted remote Administrator shell. Routine tests/verification/repository-controlled operations may run there; admin/physical/secret actions remain separately gated.

## Codespaces resource discipline

Use the smallest practical machine. Stop the codespace when not actively using it. Prefer repository-controlled devcontainer/setup so a codespace can be recreated rather than treated as durable state.

Do not store in Codespaces secrets:

- broker READ/TRADE tokens;
- Telegram/VK production credentials;
- Tailscale runtime/recovery secrets;
- BitLocker keys;
- DPAPI/runtime secret-store material;
- private portfolio/report payloads;
- Real-money confirmation/authority.

## When engineering may interrupt the OWNER

Routine code, formatting, tests, CI debugging, PR housekeeping, dependency updates and supported provider automation are engineering work, not OWNER work.

OWNER involvement is reserved for:

- initial external-account consent/credential bootstrap that no safe API can perform;
- entering a secret into an approved protected boundary;
- physical hardware/BitLocker/UEFI action;
- Windows Administrator action that cannot safely be delegated to a reviewed automation boundary;
- an irreversible/materially risky product decision explicitly reserved to OWNER;
- required security/Real-money confirmation.

## Phone-only does not weaken safety

A mobile workflow never authorizes bypassing:

- exact-head CI;
- protected `main` PR discipline;
- OWNER physical evidence where genuinely required;
- Windows-specific acceptance;
- `app:app` protected rollback;
- `trading_methods=false` / `REAL_TRADING_ENABLED=false`;
- broker-write and transfer/withdrawal prohibitions.

## Physical exception

If the node is physically dead, BitLocker/UEFI intervention is required, Windows trust/bootstrap is lost, or another reviewed admin action cannot be safely exposed remotely, the system reports `OWNER_ACTION_REQUIRED`. That is a physical recovery exception, not ordinary product/engineering UX.
