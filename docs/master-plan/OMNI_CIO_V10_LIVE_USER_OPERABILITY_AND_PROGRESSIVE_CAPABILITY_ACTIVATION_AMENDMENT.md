# Omni-CIO V10 — Live User Operability & Progressive Capability Activation Law / Amendment 13

Status: **OWNER-APPROVED GOVERNANCE AUTHORITY — EFFECTIVE WHEN PRESENT ON ACCEPTED PROTECTED `main`**  
Decision date: **2026-08-27**  
Scope: progressive live-user activation of completed capabilities, capability-state governance, canonical Web operability, tenant isolation, broker credential operability boundaries, real-money authority separation, and user-facing System Update Definition of Done.

## 1. Purpose

Omni-CIO V10 is one continuously evolving product, not a collection of dormant features waiting for a final all-at-once release.

The canonical product remains one Omni-CIO Web. A separate staging website is **not required** for ordinary product evolution. When a user-facing capability is implemented, passes its own applicable technical, security and external gates, and does not depend on unfinished higher authority, the capability must become live-operable for an ordinary authenticated USER on the canonical product instead of remaining artificially disabled merely because unrelated later V10 work is unfinished.

This amendment changes activation philosophy only. It does not itself activate a capability, mutate production infrastructure, provision a provider or broker secret, waive a broker/legal/privacy requirement, start a System Update, enable broker submit, or advance accepted V10 percentage.

## 2. Authority and precedence

The Master Plan block/WP dependency order remains unchanged. Amendment 12 remains the execution-unit and verification law. Amendment 13 governs **capability activation semantics** after implementation evidence exists.

Where older V10 text uses a blanket rule that keeps an otherwise independently completed user capability disabled until a single final launch, a later unrelated block, or V10.0.0 as a whole, this Amendment 13 supersedes that blanket coupling. Direct owning gates remain mandatory.

In particular:

- Amendment 10's public hosted target, one-account/one-tenant model, managed-cloud requirement, free initial access, tenant-owned broker credentials and legal/broker gates remain binding;
- Amendment 11's technical-closeout versus production-activation separation remains binding, but production activation is interpreted capability-by-capability where gates are separable rather than as a reason to hold unrelated completed capabilities until final V10 release;
- Amendment 12's production-cutover, security/authority, provider-action, live-evidence and Real-money mandatory split triggers remain binding;
- historical documents remain historical evidence and are not rewritten to pretend this law always existed.

## 3. One canonical live product

The product rule is:

`ordinary USER -> canonical Omni-CIO Web -> authenticated account -> isolated Tenant -> only accepted live-operable capabilities`

A second Web product, duplicate frontend, separate identity system or parallel broker stack is forbidden.

A separate staging website is not required for a capability to become live-operable. Synthetic/provider-double/technical environments may still exist as engineering evidence below a live-user boundary, and a safety-critical rollout may use staged controls on the same canonical product, but no permanent staging-only product is allowed to become the place where completed ordinary-user functionality lives while the canonical Web remains artificially dormant.

## 4. Machine-readable progressive capability states

The only accepted lifecycle states for a capability that has entered the activation ledger are:

- `IMPLEMENTED` — the capability's implementation/technical acceptance exists, but live-user activation has not yet been accepted;
- `LIVE_OPERABLE` — all direct applicable technical, security and external gates are accepted and an ordinary USER can use the capability on the canonical Omni-CIO Web;
- `BLOCKED_EXTERNAL` — implementation may exist, but one or more required external/provider/broker/legal/privacy/secret-custody/production gates lack accepted evidence; the UI and ledger must name the blocker truthfully;
- `REAL_MONEY_AUTHORIZED` — a Real-money submission capability has passed its complete owning execution/Real-money gate and is explicitly authorized for the exact reviewed authority surface.

A capability absent from the ledger has **no accepted implementation or activation authority by implication**. Absence must never be interpreted as `IMPLEMENTED`, `LIVE_OPERABLE` or `REAL_MONEY_AUTHORIZED`.

Emergency operational disablement is recorded separately from lifecycle state. A kill switch can temporarily stop a `LIVE_OPERABLE` or `REAL_MONEY_AUTHORIZED` capability without rewriting accepted historical lifecycle evidence.

## 5. Progressive activation law

For each user-facing capability:

1. identify its direct prerequisites and owning gates;
2. implement and technically accept it through the authorized execution unit;
3. evaluate security, tenant isolation, secret custody, provider, broker, privacy/legal, capacity, recovery and operational gates that are actually applicable to that capability;
4. if a required external gate lacks evidence, record `BLOCKED_EXTERNAL` and do not claim acceptance;
5. when all direct applicable gates are accepted, make the capability `LIVE_OPERABLE` for ordinary USERs on the canonical Web;
6. do not hold it disabled solely because an unrelated later V10 capability is unfinished.

Unfinished AI/Cortex, Telegram Bot, Guardian or Real-execution scope does not by itself block an independently safe Web authentication, multi-user, broker READ or other ordinary capability.

Likewise, acceptance of an unrelated capability never grants the missing authority of a higher-risk capability.

## 6. Product authentication and multi-user activation

Telegram Login and VK ID remain the only ordinary human product-login providers. GitHub, Windows, cloud-provider, CI, OWNER/admin/developer/demo/preview identities remain outside product authentication.

Once production Telegram/VK configuration, callback registration and the directly applicable production security/privacy/capacity/operations gates are accepted, authentication must become `LIVE_OPERABLE` without waiting for V10.0.0 or Telegram Bot Block F.

Multi-user tenant access follows the same rule. It may become `LIVE_OPERABLE` after the required account/session, database/RLS, cross-tenant isolation, recovery, abuse/capacity, privacy/personal-data and production-operation gates pass. Unrelated future AI or Real-execution work is not an activation prerequisite.

`PUBLIC_MULTI_USER_ENABLED` is therefore a reviewed activation/emergency control owned by the multi-user capability gate, not a permanent blanket V10-development lock. It remains `false` until that capability's own activation evidence is accepted. Amendment 13 does **not** change its current value.

## 7. T-Invest READ capability is independent of Real execution

The tenant ownership model remains:

`USER -> Tenant -> BrokerConnection -> READ credential -> verified broker accounts`

After the exact public broker-terms/permission, production security, tenant-scoped secret-custody, privacy/legal and operational gates applicable to READ are accepted, the authenticated USER must be able to provision/replace/revoke a READ credential and use accepted real broker-backed read capabilities on the canonical Web.

READ live operability includes only reviewed read-side data such as account discovery, portfolio, positions and operations supported by the accepted connector contracts. It must not wait for Real execution.

A READ credential never authorizes order submission. Full-access/TRADE authority must never be used as a fallback for portfolio reads.

The current T-Invest public-service gate remains fail-closed until real evidence changes it. A user-supplied token does not waive broker terms.

## 8. TRADE credential connection is not broker-submit authority

After the tenant-scoped TRADE provisioning flow itself passes its security, secret-custody, provider/broker and account-binding gates, an authenticated USER may connect, validate, replace and revoke a TRADE credential on the canonical Web.

The required account rule remains:

`EXECUTABLE_ACCOUNTS = VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS`

A TRADE credential may be recorded as connected/verified only for the submitting tenant and only with verified broker-account identity binding. Cross-tenant reuse is forbidden.

The following invariant is absolute:

`TRADE credential connected != real broker submit authorized`

A connected TRADE credential may therefore coexist with broker submit being unavailable. The UI must present that distinction explicitly and must not imply Real execution authority.

Raw broker credentials never enter browser Web Storage, GitHub, CI logs, artifacts, screenshots, issue/PR text, chat or Cortex context.

## 9. Real-money authorization remains a separate high-risk gate

`REAL_MONEY_AUTHORIZED` is reserved for the actual broker-submit capability. It is never assigned merely because a TRADE credential exists.

Before Real order submission can become `REAL_MONEY_AUTHORIZED`, the owning execution contour must have accepted evidence for all applicable safeguards, including:

- Sandbox and/or mandatory Shadow evidence required by the owning execution package;
- exact immutable plan identity and approval;
- authenticated USER approval for that USER's own tenant/account;
- fresh preflight and policy checks;
- READ/TRADE verified-account intersection;
- own cash / owned free quantity constraints;
- drift detection and stop/re-plan behavior;
- idempotent submit identity;
- ambiguous-submit reconciliation before any retry;
- broker reconciliation and submitted-versus-filled truth;
- durable audit/evidence;
- independent emergency kill switches.

`REAL_TRADING_ENABLED=false` and `trading_methods=false` remain protected current defaults. Amendment 13 does not flip either value.

## 10. Authority that is not expanded

This amendment does not add or expand:

- transfers or withdrawals;
- margin or leverage;
- uncovered short positions;
- arbitrary broker methods;
- autonomous discretionary Real trading;
- AI/Cortex broker-write authority;
- shared/global broker credentials;
- cross-tenant secret/data access.

Transfer-access authority remains outside the accepted V10 ordinary BUY/SELL scope unless a later explicit OWNER-approved amendment changes it.

## 11. Emergency kill switches

A capability that is `LIVE_OPERABLE` or `REAL_MONEY_AUTHORIZED` must retain an owning emergency disable/rollback mechanism where its risk profile requires one.

A kill switch is an incident-safety mechanism, not a permanent substitute for completing activation work. It must be observable, auditable and reversible through the owning recovery procedure.

Real-money kill switches remain independent from read-only portfolio functionality wherever safe so that disabling execution does not unnecessarily destroy read-only observability.

## 12. Definition of Done for user-facing System Updates

For a user-facing capability or System Update that claims `LIVE_OPERABLE`, repository/CI completion alone is insufficient. Definition of Done includes all applicable evidence below:

- accepted implementation and exact-head verification;
- deployment to the canonical Omni-CIO Web or accepted canonical production boundary;
- ordinary USER path, without OWNER/admin/demo/session-minting bypass;
- real-user operability evidence using a non-secret result contract;
- multi-user/tenant isolation evidence when more than one tenant is supported;
- application authorization plus database-enforced isolation where applicable;
- secret/private-data exclusion from source/CI/artifacts/chat;
- health/monitoring/degraded-state behavior;
- rollback/recovery path;
- direct external/provider/legal/broker evidence where applicable;
- capability ledger transition with evidence links;
- no claim that a missing external gate passed merely because code or synthetic tests passed.

For multi-user capabilities, deterministic cross-tenant negative tests remain mandatory even when controlled real-user acceptance is also performed. Real-user evidence must not require exposing another tenant's private payload.

## 13. Capability Activation Ledger

`docs/operations/V10_CAPABILITY_ACTIVATION_LEDGER.json` is the machine-readable capability-state ledger.

It is **not** a second V10 progress/current-WP ledger. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` remains the sole accepted V10 progress/current-next execution authority.

Each tracked capability records:

- stable capability ID;
- lifecycle state;
- implementation evidence;
- direct gates;
- accepted evidence references;
- external blockers when state is `BLOCKED_EXTERNAL`;
- emergency/operational control metadata;
- last accepted transition date.

The ledger must never contain raw secrets, full account identifiers, private portfolio payloads or fabricated OWNER/external evidence.

## 14. GitHub-visible capability dashboard

Capability activation work uses `.github/ISSUE_TEMPLATE/v10_capability_activation.yml` for a GitHub-visible dashboard when an activation transition is being executed or reviewed.

The dashboard is a working/evidence view. It must state:

`CAPABILITY ACTIVATION WORKING STATE — NOT V10 PROGRESS AUTHORITY`

A dashboard checkbox or issue comment cannot activate a capability by itself. Accepted activation comes only from the owning accepted-main evidence chain and the capability ledger transition.

## 15. Amendment 12 interaction

A production cutover, security/authority transition, non-delegable provider action, live/temporal evidence or Real-money authority remains an Amendment-12 mandatory split trigger when applicable.

Therefore a System Update may complete implementation while an individual capability remains `BLOCKED_EXTERNAL`. The later activation can be a focused change/split boundary without reopening unrelated completed implementation.

Conversely, if all direct activation evidence is available within the authorized update and no mandatory split trigger requires a separate accepted state, the capability should transition to `LIVE_OPERABLE` as part of that accepted lifecycle rather than being left dormant for an unrelated future block.

## 16. External evidence and no self-certification

Engineering may prove code, tests, configuration contracts and security properties it actually controls. It must not self-certify broker terms, legal permission, provider-console state, personal-data compliance, recurring-cost authority or other external facts without real evidence.

When an external requirement is unresolved, the correct state is `BLOCKED_EXTERNAL` with a precise non-secret blocker. “Provider supports this technically” is not proof that a public multi-user product is contractually permitted to use it.

## 17. Protected V9 and repository boundaries

The following remain protected:

- one product and one source-controlled Web App;
- stable V9 Gateway entrypoint `app:app` until its owning parity/decommission gate;
- protected V9 rollback;
- tenant isolation;
- secret/private-data separation;
- squash merge;
- zero unresolved blocking review threads;
- SUCCESS-only applicable exact-head verification;
- exact-new-main post-merge Regression Shield;
- no temporary verifier commits/PRs/branches.

## 18. Acceptance effect of Amendment 13

Acceptance of Amendment 13 has **no immediate runtime mutation** and **no product-progress credit**.

After Amendment 13 is accepted:

- accepted V10 implementation progress remains **54%**;
- product implementation remains **PAUSED**;
- `WEB-VISUAL-INTEGRATED` remains the next prepared System Update;
- exact OWNER START remains required before product implementation;
- `PUBLIC_MULTI_USER_ENABLED` remains unchanged/currently false;
- `trading_methods=false` remains unchanged;
- `REAL_TRADING_ENABLED=false` remains unchanged;
- broker write remains OFF;
- current T-Invest public connector remains `BLOCKED_EXTERNAL` / fail-closed pending real broker-terms evidence;
- no real provider/broker secret is requested or provisioned by this governance change.

The exact product START command remains:

`START V10 WEB VISUAL SYSTEM UPDATE`

After post-merge acceptance of Amendment 13, engineering must stop and wait for a separate OWNER START before `WEB-VISUAL-INTEGRATED` or any other product implementation begins.

## 19. Amendment 13 acceptance gate

Amendment 13 becomes active authority only after its governance PR:

1. is based on the current accepted `main` after Amendment-12 post-merge acceptance;
2. contains only governance/contracts/guards/tests/templates and no product/runtime implementation;
3. has all applicable exact-head DRAFT checks actually conclude `success`;
4. has independent review with zero unresolved blocking threads;
5. has a fresh READY exact-head applicable cycle conclude `success`;
6. is squash-merged through protected `main`;
7. has required exact-new-main Regression Shield and governance post-merge checks conclude `success`.

Only then is this amendment accepted. A pending, cancelled, skipped, neutral or failed applicable gate is not GREEN.
