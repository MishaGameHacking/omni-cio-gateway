# Omni-CIO V10 — Live User Operability & Progressive Capability Activation Law / Amendment 13

**Status:** OWNER-APPROVED / EFFECTIVE ONLY WHEN ACCEPTED ON PROTECTED `main`  
**OWNER decision:** 2026-08-27  
**Scope:** V10 user-facing capability activation, live-user acceptance, broker credential operability and Real-money authority separation  
**Product progress effect:** NONE by itself  
**Runtime mutation effect:** NONE by itself

## 1. Purpose

This amendment replaces the blanket “implement now, unlock everything only at one later release/cutover” interpretation with **progressive capability activation**.

The product goal is one canonical Omni-CIO Web that real supported users can use as a real product while V10 continues to evolve. A separate user-facing staging product is not required merely to validate ordinary completed capabilities.

A user-facing capability that is implemented and has passed every gate that actually owns that capability must become live-operable without waiting for unrelated later V10 blocks or the final `V10.0.0` release.

This law removes artificial development locks. It does **not** invent provider permission, broker permission, privacy/legal acceptance, secret-custody acceptance, capacity/operations evidence or Real-money authority.

## 2. Precedence and exact supersession

The Master Plan block order, weights and all non-conflicting amendments remain binding.

Where activation timing conflicts, Amendment 13 explicitly supersedes only the older blanket interpretation in Amendments 10, 11 and 12 that normal user-facing capabilities must remain unavailable until one monolithic `PUBLIC_PRODUCTION_ACTIVATION` or final V10 release.

The following older requirements remain active and are not weakened:

- final public service must use an accepted managed-cloud/runtime boundary and must not depend on PROJECT OWNER home infrastructure;
- provider credentials/callback registration require real provider configuration and must never be fabricated;
- tenant/session/authentication security and database isolation remain mandatory;
- public T-Invest remains fail-closed until broker-terms/permission and secret-custody/security/privacy gates are actually accepted;
- Real broker submit remains separately gated;
- transfer/withdrawal, margin/leverage and uncovered-short authority are not introduced;
- `app:app` protected V9 recovery/rollback remains intact;
- exact-head SUCCESS-only verification, squash merge and post-merge Regression Shield remain binding;
- Amendment 12 execution-unit/HEAD-FREEZE/batch-correction discipline remains active.

Historical Amendment-10/11/12 files remain historical accepted evidence and are not rewritten as if this rule always existed.

## 3. One canonical Web / no second product

The user-facing baseline is one canonical Omni-CIO Web product.

Rules:

- do not create a second “test Omni-CIO”, second frontend, second account system or second production-facing URL merely to let the OWNER/users test completed functionality;
- real USER acceptance should use the same authentication/account/tenant/product path intended for ordinary users;
- local, CI, deterministic provider doubles, synthetic fixtures, T-Invest Sandbox and Shadow Mode remain allowed engineering/safety contours;
- those engineering contours are not a second product and never become an authentication/tenant bypass;
- a capability is not `LIVE_OPERABLE` merely because a synthetic or sandbox test passed.

## 4. Canonical progressive capability states

Exactly four machine-readable activation states are used for implemented/activation-tracked capabilities:

1. `IMPLEMENTED`
2. `LIVE_OPERABLE`
3. `BLOCKED_EXTERNAL`
4. `REAL_MONEY_AUTHORIZED`

Capabilities that are not yet implemented remain governed by Master Plan/WP status and must not be assigned one of these states merely to make a dashboard look complete.

### 4.1 `IMPLEMENTED`

Code/contracts/tests are accepted, but live user operability has not yet been proven or activated.

This state is not permission to claim that a real user can use the capability.

### 4.2 `BLOCKED_EXTERNAL`

The repository-side implementation may be accepted, but a real external prerequisite still blocks live operation, for example:

- provider application/Allowed URL/callback registration;
- provider runtime credential provisioning;
- broker terms/permission;
- approved hosted secret custody;
- privacy/personal-data/legal acceptance;
- managed-runtime/hostname/DNS/edge readiness;
- capacity/monitoring/incident-operations acceptance;
- bounded OWNER/provider action that cannot be delegated.

A blocker must be specific and evidence-backed. “V10 is not finished yet” is not a valid external blocker.

### 4.3 `LIVE_OPERABLE`

An ordinary supported USER can use the capability end-to-end on the canonical Omni-CIO Web after all owning technical, security and external gates are accepted.

`LIVE_OPERABLE` does not imply Real-money broker-submit authority.

A capability already `LIVE_OPERABLE` must not be deliberately held disabled solely because an unrelated future block is incomplete.

### 4.4 `REAL_MONEY_AUTHORIZED`

This state is reserved for the real broker-submit capability after its full execution/authority gate.

No login, UI, AI, Telegram, READ credential, TRADE credential, plan draft, GitHub merge, System Update, OWNER feedback or `LIVE_OPERABLE` state automatically implies `REAL_MONEY_AUTHORIZED`.

## 5. Allowed state transitions

Normal transitions are fail-closed:

`IMPLEMENTED -> LIVE_OPERABLE` when all owning gates are already satisfied.

`IMPLEMENTED -> BLOCKED_EXTERNAL` when one or more real external gates remain.

`BLOCKED_EXTERNAL -> LIVE_OPERABLE` only after the missing external evidence/action is actually accepted.

Real submit follows a separate path and may become `REAL_MONEY_AUTHORIZED` only after the owning execution contour has completed its required Shadow/Sandbox, approval, drift, reconciliation and kill-switch gates plus external broker permission.

A governance amendment by itself never performs any of these runtime transitions.

## 6. Real-user operability is part of Definition of Done

For every user-facing System Update/capability where live operation is technically and externally possible, final acceptance evidence must include the applicable sequence:

`automated verification -> canonical deployed Web -> real supported USER interaction -> multi-user isolation negatives where applicable -> monitoring/revoke/rollback/recovery -> capability-state decision`.

A capability must not be called live-accepted solely because unit/CI/provider-double tests pass when real-user operation is available and safe to prove.

Real-user evidence must remain sanitized. No provider secret, broker token, full broker account ID or private portfolio payload may be stored in GitHub, CI logs, screenshots or artifacts.

## 7. Multi-user live acceptance

When authentication and public-user activation gates are satisfied, real users may exercise the same ordinary product path concurrently:

`Telegram Login | VK ID -> verified external identity -> OmniCIOUserAccount -> Tenant -> server-side Session`.

Live acceptance must prove at least:

- USER A cannot read or mutate USER B tenant state;
- guessed object IDs do not authorize cross-tenant access;
- sessions/logout/revocation remain user-scoped;
- cache/background-job/notification paths preserve tenant scope where applicable;
- one user's provider/broker credentials are inaccessible to other tenants.

The PROJECT OWNER tests as an ordinary USER, not through an OWNER/admin login bypass.

## 8. Telegram Login and VK ID progressive activation

WP22A has accepted the technical Telegram/VK authentication architecture. That does not mean the current hosted environment already possesses real provider registration or secrets.

Telegram Login or VK ID moves from `BLOCKED_EXTERNAL` to `LIVE_OPERABLE` once its own real-provider and public-user gates are accepted, including the applicable:

- registered production/canonical Web origin and callback URI;
- runtime-only provider client configuration;
- cryptographic/provider validation;
- managed runtime/hostname/security acceptance;
- privacy/capacity/monitoring/incident controls;
- real browser login/logout/revocation evidence.

It does not wait for Web Visual completion, Telegram Bot Block F, AI, Guardian or final V10 release unless one of those is a demonstrated dependency.

Current official references include Telegram OIDC Authorization Code + PKCE and registered Allowed URLs (`https://core.telegram.org/bots/telegram-login`) and the first-party VK ID OAuth SDK (`https://github.com/VKCOM/vkid-web-sdk`).

## 9. T-Invest READ is independent from Real execution

A tenant-owned READ credential is a normal read capability, not Real-money execution authority.

Once the public T-Invest terms/permission gate, approved tenant-scoped secret custody, privacy/security and live broker-connection acceptance are actually satisfied, the canonical Web may make the following `LIVE_OPERABLE` independently of unfinished Real execution:

- READ credential provisioning/replacement/revocation;
- broker-account discovery and verified binding;
- real portfolio;
- positions;
- permitted operations/history;
- current market/read enrichment supported by the accepted read contract.

The existing structural rule remains: a TRADE/full-access credential must never be used as a fallback for READ operations.

Current T-Invest documentation explicitly distinguishes Read-only tokens (cannot place orders), Full-access tokens, Transfer-access tokens, account-specific tokens and Sandbox tokens: `https://developer.tbank.ru/invest/intro/intro/token`.

User-supplied tokens do not waive broker terms. Until actual permission/terms and custody gates are accepted, public T-Invest stays `BLOCKED_EXTERNAL` / `FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION`.

## 10. TRADE credential connection is not broker-submit authority

When the owning future Web/security provisioning flow is implemented and accepted, an authenticated USER may connect/replace/revoke and validate a tenant-scoped `TRADE` credential without that act authorizing a real order.

Before an account can ever be execution-eligible, Omni-CIO must independently verify the same broker-account identity on both READ and TRADE sides:

`EXECUTABLE_ACCOUNTS = VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS`

A mismatch fails closed.

`TRADE credential connected/verified` means only that the credential role and account intersection are valid. It does not mean `REAL_MONEY_AUTHORIZED`.

Raw READ/TRADE credentials remain backend-only, encrypted/secret-managed according to the accepted design, never returned to the browser after submission, never stored in Web Storage and never exposed to Cortex/GitHub/CI/other tenants.

## 11. Sandbox / Shadow / Real execution ladder

The same canonical Web may use safe execution contours as they become implemented; a second Omni-CIO site is not required.

The required progression remains:

`deterministic execution tests -> T-Invest Sandbox where applicable -> Shadow Mode/live read evidence -> immutable exact plan -> USER approval/step-up -> drift/preflight -> broker submit -> reconciliation`.

T-Invest Sandbox is a separate virtual contour and does not mutate the user's real portfolio; it may be used to prove execution UX/adapter behavior but is not real execution evidence.

Real broker submit may become `REAL_MONEY_AUTHORIZED` only after the owning Block-I gates accept at minimum:

- representative Shadow/Sandbox evidence;
- immutable plan binding;
- exact account/instrument/side/quantity/price/limits;
- authenticated short-lived USER approval;
- immediate preflight and drift-stop/re-plan behavior;
- idempotency and one-possible-submit semantics;
- ambiguous-submit -> no blind retry -> reconciliation;
- kill switches and rollback;
- broker terms/permission and credential authority.

`submitted != filled` without broker evidence remains mandatory.

## 12. Authority that remains outside V10 normal user freedom

This amendment does not authorize:

- transfer/withdrawal/securities transfer;
- margin/leverage;
- uncovered short;
- autonomous recurring Real-money execution without the owning approved contract;
- provider/broker/admin secret exposure;
- cross-tenant administration;
- AI direct broker-submit authority;
- payment/provider spend above the accepted OWNER budget.

T-Invest documents Transfer-access as a distinct broader token authority; Omni-CIO does not infer that authority from ordinary BUY/SELL capability.

## 13. Emergency kill switches versus artificial locks

Kill switches remain mandatory safety mechanisms.

A kill switch may temporarily suspend a `LIVE_OPERABLE` or `REAL_MONEY_AUTHORIZED` capability because of incident, stale dependency, security concern, reconciliation uncertainty or external provider failure.

This is different from an artificial development lock:

- accepted capability state is recorded separately from current runtime availability;
- temporary suspension must expose a truthful reason/status;
- recovery requires the owning readiness criteria;
- a kill switch is not used as the permanent normal state of a capability whose gates are already satisfied.

## 14. UI truthfulness

The Web must not present a completed/advertised capability as a button that appears broken or silently does nothing.

If a capability is live, it works for an authorized USER.

If it is blocked, the UI/status should expose the truthful bounded state/reason such as `BLOCKED_EXTERNAL`, provider not configured, broker terms pending, Shadow Mode or temporary safety suspension.

The UI must never suggest real trading is authorized when the system is only validating a TRADE credential or running Sandbox/Shadow.

## 15. Capability Activation Ledger / dashboard

Every material user-facing activation transition must use:

- branch/working ledger template: `docs/updates/V10_CAPABILITY_ACTIVATION_LEDGER_TEMPLATE.md`;
- GitHub-visible dashboard template: `.github/ISSUE_TEMPLATE/v10_capability_activation.yml`.

Both must state:

`WORKING CAPABILITY ACTIVATION STATE — NOT ACCEPTED MAIN AUTHORITY`.

They track capability ID, implementation evidence, current/proposed activation state, external blockers, real-user evidence, multi-user isolation evidence, secret/privacy/terms gates, monitoring/rollback and kill-switch state.

They never replace `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` as accepted current V10 authority.

## 16. Current capability baseline at Amendment-13 acceptance

This governance amendment itself performs no provider, broker, DNS, cloud, secret or runtime mutation.

Therefore the accepted-current activation baseline remains fail-closed until later capability-specific evidence exists:

- `telegram_login`: implementation accepted, `BLOCKED_EXTERNAL`;
- `vk_id`: implementation accepted, `BLOCKED_EXTERNAL`;
- `public_multi_user_tenant_access`: technical implementation accepted, `BLOCKED_EXTERNAL`, current runtime flag remains `PUBLIC_MULTI_USER_ENABLED=false`;
- `tinvest_read`: implementation accepted, `BLOCKED_EXTERNAL`, public connector remains `FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION`.

`PUBLIC_MULTI_USER_ENABLED=false` is therefore the **current runtime state**, not a permanent V10-wide release lock. A future exact capability-specific activation may change it without waiting for unrelated later blocks, but only after all owning gates are proven and accepted.

Likewise `trading_methods=false`, broker write OFF and `REAL_TRADING_ENABLED=false` remain current protected defaults. Only the later owning execution/Real-money gate may change them.

## 17. Product-development sequencing remains paused

Amendment 13 changes activation policy, not the current System Update START state.

After this governance amendment is accepted:

- accepted V10 progress remains 54%;
- `PRODUCT IMPLEMENTATION PAUSED` remains true;
- next prepared System Update remains `WEB-VISUAL-INTEGRATED` A→G;
- `START V10 WEB VISUAL SYSTEM UPDATE` remains required before product-source changes;
- WP23+ remains locked behind the accepted visual System Update and Master Plan sequence.

No capability activation, provider provisioning, broker credential collection or Web visual implementation is performed by this governance PR.

## 18. Governance acceptance gate

Amendment 13 becomes active only after the governance-only PR containing the synchronized amendment/contract/ledger/dashboard/live guidance/guards:

- passes all applicable exact-head DRAFT checks with `success`;
- passes independent review with zero unresolved blocking threads;
- passes a fresh READY exact-head applicable cycle with `success`;
- is squash-merged through protected `main`;
- passes exact-new-main Regression Shield and owning `V10 Engineering Governance` post-merge gate.

The PR must contain no real provider/broker secret and no product/runtime activation mutation.
