# Omni-CIO V10 — Phone Engineering Runbook

Status: **DRAFT with phone-only engineering amendment**

## Goal

The OWNER can direct development, inspect PR/CI state and perform ordinary repository work from a phone while the Windows Personal Node runs headless. Local node PowerShell is reserved for genuine physical/admin recovery only.

## Phone toolset

### Required

- ChatGPT mobile — engineering direction/orchestration.
- GitHub Mobile — notifications, PR/issues/reviews and quick file changes.
- Mobile browser signed in to GitHub — full repository/Actions/Codespaces access.

### Recommended fallback full IDE

GitHub Codespaces opened in the mobile browser. It provides browser VS Code, terminal, Git and application run/debug capability. Treat it as a disposable engineering environment; never provision production secrets into it.

### Product/private access

Tailscale mobile becomes the private transport for the WP22A phone rehearsal and, after acceptance, ordinary private phone access to the single Omni-CIO Web App. Tailscale configuration is not part of this amendment's acceptance and must still pass WP22A.

## Daily development flow

1. OWNER describes the goal in ChatGPT mobile.
2. Engineering restores GitHub source of truth and works only in the current authorized branch/WP.
3. Changes go to GitHub branch/PR; never directly to `main`.
4. GitHub-hosted checks provide acceleration when available.
5. Windows/self-hosted exact-head gates run on the headless Personal Node where required.
6. OWNER reviews only the summarized PASS/FAIL/security state from the phone.
7. Merge occurs only after the existing exact-head/threads/squash discipline is satisfied.
8. Render behavior remains governed by the existing V9 deployment contract until a responsible V10 cutover replaces it.

## Codespaces resource discipline

Use the smallest practical machine. Stop the codespace when not actively using it. Prefer repository-controlled devcontainer/setup so a codespace can be recreated rather than treated as durable state.

Do not store in Codespaces secrets:

- broker READ/TRADE tokens;
- Telegram/VK production credentials;
- Tailscale auth/recovery material;
- BitLocker keys;
- DPAPI/runtime secret-store material;
- private portfolio/report payloads;
- Real-money confirmation/authority.

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
