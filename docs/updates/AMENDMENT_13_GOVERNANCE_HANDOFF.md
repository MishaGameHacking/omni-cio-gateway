# Amendment 13 governance handoff

**FOCUSED GOVERNANCE CHANGE — NOT PRODUCT IMPLEMENTATION**

Accepted base: `4aa34b1fef89e156a88844803a2c9ec983f6fc64`  
Branch: `v10/governance-live-user-operability-law`  
Authority: OWNER-approved Amendment 13 governance-only mandate, 2026-08-27.

## Scope

This focused governance change introduces the Live User Operability & Progressive Capability Activation Law and its machine-readable contract, capability ledger, acceptance standard, dashboard template, deterministic guard and regression tests.

No `apps/web`, `apps/api`, broker runtime, provider resource, secret, public cutover or Real-money authority is changed.

## Preflight

- Amendment 12 owning post-merge Regression Shield: exact-main `success`.
- Amendment 12 governance post-merge check: exact-main `success`.
- branch compare against accepted base: ahead-only, no main drift when prepared;
- progressive activation contract/ledger JSON parse: PASS;
- new Python guard/tests compile: PASS;
- focused guard on restored contract fixture: PASS;
- 7 focused stdlib regression tests: PASS;
- secret-like literal scan of Amendment 13 changed surface: no credential material found;
- exact Ruff formatter could not be executed in the current tool runtime and remains an independent PR gate; no PASS is claimed for it.

## Current capability truth

The new capability ledger deliberately records current externally gated capabilities as `BLOCKED_EXTERNAL` and does not claim any `REAL_MONEY_AUTHORIZED` capability. Public T-Invest broker-terms permission, production broker secret custody, production Telegram/VK provider configuration, real-user cutover and production legal/privacy/capacity evidence are not claimed complete.

## Locks after acceptance

- product implementation remains `PAUSED`;
- next prepared update remains `WEB-VISUAL-INTEGRATED`;
- exact OWNER START remains `START V10 WEB VISUAL SYSTEM UPDATE`;
- `PUBLIC_MULTI_USER_ENABLED` is not changed by this amendment;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker write OFF;
- no transfer/withdrawal/margin/leverage/uncovered-short expansion;
- V9 rollback and `app:app` remain protected.

After Amendment 13 post-merge acceptance, stop and wait for a separate OWNER START.
