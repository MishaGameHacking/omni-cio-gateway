---
applyTo: "**"
---

# Omni-CIO V10 — OWNER handoff and runtime boundaries

These rules supplement repository-wide `.github/copilot-instructions.md`, root `AGENTS.md`, accepted V10 amendments and `docs/operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md`.

## OWNER help must be deterministic

When OWNER action is genuinely required, do not tell the OWNER merely to “open Settings”, “go to Billing”, “find Zero Trust”, “check the provider dashboard”, or otherwise discover the destination.

Before asking the OWNER to act:

1. verify current official provider UI/docs when navigation can change;
2. give a direct official HTTPS link to the exact stable page when such a link exists;
3. if no stable deep link can be verified, say so and give the closest verified official start URL plus exact click path;
4. identify exact account/repository/workspace/service/device scope;
5. request one bounded action only;
6. state exact expected result;
7. state STOP conditions if the UI/result differs;
8. state adjacent actions that must not be taken, especially payment, premature public ingress, destructive mutation or secret disclosure;
9. request only the minimum safe non-secret result back.

Never use shortened, third-party redirect, secret-bearing or private runtime links in OWNER instructions.

## OWNER billing / CI cost control

Never silently increase a GitHub/provider budget, disable a spending hard stop, add/replace payment information, buy a plan or authorize metered spend.

The OWNER-observed GitHub Actions zero-budget hard stop is mutable external state and must be reverified before future billing decisions; it is not permission to change it.

If a GitHub-hosted job is blocked by budget/billing:

- classify the startup block accurately as external infrastructure/cost state rather than a code defect;
- do not merge around the RED applicable check;
- do not repeatedly trigger a hosted job already known to be unable to start;
- first use semantically equivalent already-accepted/zero-cost validation where safe, especially Lenovo self-hosted CI;
- never silently remove a required hosted clean-room semantic;
- request OWNER spend only if the required verification cannot be reproduced safely without it, and state exact reason, cost exposure, alternative and rollback first.

Canonical cost-control standard: `docs/operations/V10_CI_COST_CONTROL_STANDARD.md`.

## Lenovo is engineering/recovery, not public production

The 2026-08-18 Public Free Multi-User Hosted Runtime amendment supersedes the earlier rule that the Lenovo/replacement Personal Node is the final V10 Web/API/private-state host.

Lenovo remains approved for:

- authoritative self-hosted CI/continuity;
- engineering and controlled acceptance;
- recovery rehearsal and protected rollback;
- explicitly non-production staging where approved.

Lenovo/home infrastructure must **not** be the required public-production availability anchor. Ordinary USER access must not depend on PROJECT OWNER home public IP, Wi-Fi/router/LAN, home Internet/power or Lenovo being online.

Final public V10 Web/API and required hosted private-data services must use an approved managed-cloud production runtime selected through the owning WP22A service/security/recovery gate. Do not silently select or purchase a provider; provider choice/cost must follow the accepted service-selection and OWNER budget rules.

Cloudflare may provide reviewed DNS/TLS/WAF/DDoS/edge/origin-protection functions. A Cloudflare Tunnel whose sole production origin is OWNER home Lenovo does not satisfy the final public-hosted requirement.

The existing Render.com `app:app` remains protected V9 production/recovery baseline until its responsible V10 cutover. A future V10 cloud deployment must reuse the same source-controlled Omni-CIO product and must not become a parallel Web/Core stack.

## Product identity is separate from engineering identity

The PROJECT OWNER is not a special Omni-CIO product account. GitHub/cloud-provider/Windows/CI authority never grants a product tenant/session.

Normal product authority is:

`Telegram/VK -> OmniCIOUserAccount -> Tenant -> server-side Session`

Normal broker credentials are tenant-owned `BrokerConnection` secrets, not PROJECT OWNER/global application user credentials.

## Safety

Preserve `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, tenant/broker credential separation, no transfer/withdrawal authority, protected V9 rollback and Master Plan ordering unless an owning accepted later gate explicitly changes a boundary.
