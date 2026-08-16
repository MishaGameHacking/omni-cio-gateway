---
applyTo: "**"
---

# Omni-CIO V10 — OWNER handoff and Personal-Node runtime

These rules supplement repository-wide `.github/copilot-instructions.md`, root `AGENTS.md`, the accepted V10 amendments and `docs/operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md`.

## OWNER help must be deterministic

When OWNER action is genuinely required, do not tell the OWNER merely to “open Settings”, “go to Billing”, “find Zero Trust”, “check the provider dashboard”, or otherwise discover the destination.

Before asking the OWNER to act:

1. verify the current official provider UI/docs when the navigation can change;
2. give a direct official HTTPS link to the exact stable page when such a stable link exists;
3. if no stable exact deep link can be verified, state that fact and give the closest verified official start URL plus the exact click path;
4. identify the exact account/repository/workspace/service/device scope;
5. give one bounded action only;
6. state the exact expected result;
7. state STOP conditions if the UI/result differs;
8. state adjacent actions that must not be taken, especially payment, public ingress, new service creation, destructive mutation or secret disclosure;
9. request only the minimum safe non-secret result back.

Never use shortened, third-party redirect, secret-bearing or private runtime links in OWNER instructions.

## OWNER billing / CI cost control

Never silently increase a GitHub/provider budget, disable a spending hard stop, add/replace payment information, buy a plan or authorize metered spend.

The 2026-08-16 OWNER screenshot confirms that the personal GitHub Actions budget is currently USD 0 with stop-usage enabled. Treat that as a mutable external-state observation that must be reverified before future billing decisions, not as permission to change it.

If a GitHub-hosted job is blocked by budget/billing:

- classify the startup block accurately as external infrastructure/cost state rather than a code defect;
- do not merge around the RED applicable check;
- do not repeatedly trigger a hosted job already known to be unable to start;
- first seek semantically equivalent zero-cost/already-paid validation, especially the accepted Lenovo self-hosted runner where appropriate;
- never silently remove a required hosted clean-room semantic;
- request OWNER spend only if the required verification cannot be reproduced safely without it, and state exact reason, cost exposure, alternative and rollback before the OWNER acts.

Canonical cost-control standard: `docs/operations/V10_CI_COST_CONTROL_STANDARD.md`.

## V10 Web runs on the Personal Node

For V10, the approved Lenovo/replacement Personal Node is the primary Web/API/runtime host. Build/render/serve the source-controlled V10 Web there according to the owning deployment contract.

Do not treat Render.com as the V10 hosting target. Do not create a new Render.com Web Service, worker, database or paid V10 deployment unless a later OWNER-approved amendment explicitly authorizes that change.

The existing Render.com `app:app` service is only the protected V9 production/recovery baseline until its responsible V10 parity/decommission gate. Preserve it; do not confuse it with local V10 rendering/serving.

A reviewed WP22A provider such as Cloudflare may provide access/security transport to the Personal Node. It must not silently become the authoritative V10 application/private-state host.

Preserve `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, broker credential separation, no transfer/withdrawal authority, protected V9 rollback and Master Plan ordering.
