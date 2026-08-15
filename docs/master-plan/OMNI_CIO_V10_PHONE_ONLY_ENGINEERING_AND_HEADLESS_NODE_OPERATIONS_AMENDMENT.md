# Omni-CIO V10 — Phone-Only Engineering / Headless Personal Node Operations Amendment

Status: **OWNER-APPROVED DRAFT — requires PR/CI/merge before becoming accepted authority**

Date: 2026-08-15

## 1. Purpose

The OWNER's normal engineering and product-control workflow moves to the phone. The first Lenovo remains a replaceable headless Personal Node / Windows self-hosted CI continuity machine until a later reviewed replacement-node cutover. This amendment does not create a second product, second repository, second Web App, or competing runtime stack.

## 2. Primary OWNER surfaces

Normal OWNER interaction after the transition is:

1. ChatGPT mobile for engineering direction and GitHub-connected development orchestration;
2. GitHub Mobile / mobile GitHub Web for PR, issue, review, Actions and repository control;
3. GitHub Codespaces in a mobile browser as the fallback full development environment when direct file/terminal work is required;
4. Omni-CIO Web on the phone as the ordinary product and operational UI once the responsible Web/WP22A gates are accepted.

Local Lenovo PowerShell is not a routine OWNER UX.

## 3. GitHub/Codespaces engineering boundary

GitHub remains the engineering source of truth. GitHub Pro included capabilities are consumed before proposing another recurring paid engineering platform.

Codespaces is an engineering clean-room/fallback environment only. It may edit, build and test repository code using synthetic/sanitized fixtures, but it must never hold production broker credentials, Tailscale auth keys, runtime DPAPI material, private portfolio payloads, BitLocker recovery material or Real-money authority.

Windows-specific/security/runtime acceptance remains on reviewed Windows/self-hosted gates. A Linux Codespace PASS never replaces a Windows exact-head gate.

## 4. Headless node contract

The Lenovo/new Personal Node must operate without an OWNER keeping a terminal open. Routine reboot recovery, service supervision, scheduled work, backup and normal Web operation must be automatic/fail-closed according to accepted V10 contracts.

Routine OWNER operations that are safe to expose remotely should be implemented through the existing Omni-CIO Web/System surface using typed, allowlisted, audited operations rather than arbitrary shell execution.

The Web control plane must not expose unrestricted PowerShell, unrestricted filesystem mutation, unrestricted SQL, GitHub bypass, secret export, broker credential disclosure, transfer/withdrawal authority or Real-money approval bypass.

## 5. Physical/admin exception boundary

Phone-only means normal operation and engineering do not require local-console use. It cannot eliminate genuinely physical recovery operations such as failed hardware replacement, firmware/UEFI intervention, BitLocker recovery, initial trust bootstrap, or other OS/admin actions that cannot be safely delegated.

When such an action is unavoidable, the existing OWNER hand-off rule remains: one reviewed idempotent operation, Administrator only when necessary, PASS/FAIL evidence only, and no secrets in chat/GitHub.

## 6. Service/cost policy

Priority order for engineering/operations services:

1. already-paid GitHub Pro capabilities;
2. free/open-source/self-hosted capabilities already compatible with V10;
3. free tiers that preserve V10 security/recovery requirements;
4. paid service only when the free/GitHub/self-hosted option is demonstrably insufficient for reliability, security, capacity or support.

A new recurring paid engineering/operations service still requires the existing cost/lock-in/fallback analysis and OWNER approval.

Free service limitations must never be hidden. A free tier that sleeps, loses durable state, weakens recovery, or cannot satisfy availability/security requirements cannot be treated as production-equivalent merely because it costs zero.

## 7. Render boundary

The accepted V9 `app:app` Render service remains the protected V9 production/recovery baseline until a responsible V10 parity/decommission gate replaces it. Phone-only engineering does not move private V10 state or broker secrets into Render and does not turn Render into a competing V10 Personal Node.

## 8. WP22A interaction

WP22A remains the current functional package and is not renumbered or bypassed by this amendment. Its draft PR remains unaccepted until its own exact-head code/security/OWNER evidence gates pass.

The phone-only direction strengthens the intended WP22A outcome: the OWNER must be able to reach the existing single Omni-CIO Web App securely from the phone without public Funnel/public ingress and without local Lenovo console use for routine access.

Any machine-bound evidence must be re-proven on the actual Personal Node used for the final WP22A acceptance.

## 9. Safety invariants

This amendment does not change:

- protected V9 `app:app` rollback;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker READ/Sandbox/Real credential separation;
- no transfer/withdrawal authority;
- PR + exact-head CI + squash merge discipline;
- GitHub as engineering source of truth;
- private durable state / GitHub source / runtime secrets separation.

## 10. Acceptance

This amendment becomes active only after its focused PR passes required checks, is squash-merged to `main`, and any required post-merge Regression Shield is GREEN.
