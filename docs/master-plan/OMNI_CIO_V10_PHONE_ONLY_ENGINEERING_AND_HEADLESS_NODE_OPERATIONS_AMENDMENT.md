# Omni-CIO V10 — Phone-Only Engineering / Headless Personal Node Operations Amendment

Status: **OWNER-APPROVED DRAFT — requires PR/CI/merge before becoming accepted authority**

Date: 2026-08-15

## 1. Purpose

The OWNER's normal engineering and product-control workflow moves to the phone. The first Lenovo remains a replaceable headless Personal Node / Windows self-hosted CI continuity machine until a later reviewed replacement-node cutover. This amendment does not create a second product, second repository, second Web App, or competing runtime stack.

The permanent engineering objective is stronger than merely opening GitHub from a phone: **GitHub is the automation hub for development and connected engineering services.** After a bounded one-time provider/account bootstrap, ordinary code, test, review, CI, deployment and supported infrastructure operations must be driven from source-controlled GitHub workflows/APIs rather than recurring OWNER dashboard clicking or local PowerShell.

## 2. Primary OWNER surfaces

Normal OWNER interaction after the transition is:

1. ChatGPT mobile for engineering direction and GitHub-connected development orchestration;
2. GitHub Mobile / mobile GitHub Web for PR, issue, review, Actions and repository control;
3. GitHub Codespaces in a mobile browser as the fallback full development environment when direct file/terminal work is required;
4. Omni-CIO Web on the phone as the ordinary product and operational UI once the responsible Web/WP22A gates are accepted.

Local Lenovo PowerShell is not a routine OWNER UX. External provider dashboards are setup/recovery surfaces, not the normal development loop.

## 3. GitHub-first autonomous engineering contract

GitHub remains the engineering source of truth and the primary automation/control plane. The engineering agent is expected to perform directly through GitHub whenever supported:

- read the accepted authority chain and current code;
- create/update focused branches and files;
- create/update PRs and issue/review state;
- inspect exact-head diffs, checks, Actions jobs and logs;
- fix code/test/CI failures at their root cause;
- maintain source-controlled deployment/infrastructure workflows;
- progress the current authorized WP without OWNER hand-holding until a real OWNER-only boundary is reached.

Connected services should be integrated behind repository-controlled Actions/API/CLI automation where the provider exposes a reviewed machine interface. Preferred authentication order is:

1. short-lived workload/federated identity where the provider supports it;
2. narrowly scoped provider credential stored only in GitHub Actions/Environment secrets;
3. bounded deploy hook/token only when no stronger supported mechanism is practical;
4. recurring manual dashboard operation only when the provider has no safe automation interface.

Provider credentials are bootstrap/configuration material, not source code. They must never be committed, echoed to logs, copied into Codespaces, or returned to the OWNER after storage.

A connected-service automation must be least-privilege and fail-closed. GitHub access does not imply broker, Real-money, secret-export, Windows Administrator or arbitrary infrastructure authority.

## 4. GitHub Actions as automation bus

Routine automation should converge on source-controlled GitHub Actions rather than OWNER clicks. Actions may coordinate supported external systems only within the owning V10 contract, for example:

- CI/test/security/release validation;
- Render deployment through its existing Git integration or a protected deploy/API credential when explicitly required by the owning deployment contract;
- Tailscale CI/private-infrastructure connectivity through its supported GitHub integration and short-lived/federated identity where accepted by WP22A;
- dependency/update automation already governed by repository policy;
- bounded read-only health/deployment verification;
- headless Windows jobs through the existing least-privilege self-hosted runner.

The Actions bus must not become a hidden Administrator shell. Risky machine mutations, secret provisioning, physical trust bootstrap, ruleset bypass, destructive recovery and Real-money operations remain separately gated.

## 5. GitHub/Codespaces engineering boundary

GitHub Pro included capabilities are consumed before proposing another recurring paid engineering platform.

Codespaces is an engineering clean-room/fallback environment only. It may edit, build and test repository code using synthetic/sanitized fixtures, but it must never hold production broker credentials, Tailscale runtime/recovery secrets, runtime DPAPI material, private portfolio payloads, BitLocker recovery material or Real-money authority.

Windows-specific/security/runtime acceptance remains on reviewed Windows/self-hosted gates. A Linux Codespace PASS never replaces a Windows exact-head gate.

## 6. Headless node contract

The Lenovo/new Personal Node must operate without an OWNER keeping a terminal open. Routine reboot recovery, service supervision, scheduled work, backup and normal Web operation must be automatic/fail-closed according to accepted V10 contracts.

Routine OWNER operations that are safe to expose remotely should be implemented through the existing Omni-CIO Web/System surface using typed, allowlisted, audited operations rather than arbitrary shell execution.

The Web control plane must not expose unrestricted PowerShell, unrestricted filesystem mutation, unrestricted SQL, GitHub bypass, secret export, broker credential disclosure, transfer/withdrawal authority or Real-money approval bypass.

The self-hosted GitHub runner stays non-admin/least-privilege. If an operation genuinely requires Administrator or physical ownership, it cannot be smuggled into routine CI merely to remove OWNER interaction.

## 7. One-time setup versus recurring OWNER work

Acceptable OWNER participation is deliberately front-loaded and rare:

- initial sign-in/authorization to a provider;
- creation of a provider OAuth/federated identity or narrowly scoped API/deploy credential when GitHub cannot create it itself;
- storing the resulting value once into the reviewed GitHub secret/environment boundary without exposing it to chat;
- physical/firmware/BitLocker/hardware action;
- an explicit OWNER decision or security/Real-money approval required by the Master Plan.

Not acceptable as the normal workflow:

- asking the OWNER to manually copy code between systems;
- repeated dashboard deploy buttons when a safe provider API/Git integration exists;
- repeated local PowerShell for routine development or service operation;
- asking the OWNER to inspect ordinary CI logs or fix ordinary code failures;
- making the phone act as the durable runtime, database or secret vault.

## 8. Physical/admin exception boundary

Phone-only means normal operation and engineering do not require local-console use. It cannot eliminate genuinely physical recovery operations such as failed hardware replacement, firmware/UEFI intervention, BitLocker recovery, initial trust bootstrap, or other OS/admin actions that cannot be safely delegated.

When such an action is unavoidable, the existing OWNER hand-off rule remains: one reviewed idempotent operation, Administrator only when necessary, PASS/FAIL evidence only, and no secrets in chat/GitHub.

## 9. Service/cost policy

Priority order for engineering/operations services:

1. already-paid GitHub Pro capabilities;
2. free/open-source/self-hosted capabilities already compatible with V10;
3. free tiers that preserve V10 security/recovery requirements;
4. paid service only when the free/GitHub/self-hosted option is demonstrably insufficient for reliability, security, capacity or support.

A new recurring paid engineering/operations service still requires the existing cost/lock-in/fallback analysis and OWNER approval.

Free service limitations must never be hidden. A free tier that sleeps, loses durable state, weakens recovery, or cannot satisfy availability/security requirements cannot be treated as production-equivalent merely because it costs zero.

## 10. Render boundary

The accepted V9 `app:app` Render service remains the protected V9 production/recovery baseline until a responsible V10 parity/decommission gate replaces it. Phone-only engineering does not move private V10 state or broker secrets into Render and does not turn Render into a competing V10 Personal Node.

Where the accepted Render deployment contract permits automation, GitHub integration/CI/API/deploy hooks should replace recurring OWNER deploy clicking. Any Render API key or deploy-hook URL is a secret and must live only in the reviewed GitHub secret boundary.

## 11. WP22A / Tailscale interaction

WP22A remains the current functional package and is not renumbered or bypassed by this amendment. Its draft PR remains unaccepted until its own exact-head code/security/OWNER evidence gates pass.

The phone-only direction strengthens the intended WP22A outcome: the OWNER must be able to reach the existing single Omni-CIO Web App securely from the phone without public Funnel/public ingress and without local Lenovo console use for routine access.

Where WP22A accepts GitHub-to-tailnet automation, prefer Tailscale's supported GitHub integration with workload/federated identity or a narrowly scoped OAuth client over a long-lived reusable auth key. Machine/user identity boundaries from WP22A remain authoritative and cannot be bypassed by CI automation.

Any machine-bound evidence must be re-proven on the actual Personal Node used for final WP22A acceptance.

## 12. Safety invariants

This amendment does not change:

- protected V9 `app:app` rollback;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker READ/Sandbox/Real credential separation;
- no transfer/withdrawal authority;
- PR + exact-head CI + squash merge discipline;
- GitHub as engineering source of truth;
- private durable state / GitHub source / runtime secrets separation.

## 13. Acceptance

This amendment becomes active only after its focused PR passes required checks, is squash-merged to `main`, and any required post-merge Regression Shield is GREEN.
