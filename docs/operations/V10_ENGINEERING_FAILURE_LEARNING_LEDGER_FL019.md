# FL-019 — Architecture amendments must update every executable authority consumer

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR PR #329; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-18**  
WP / PR / reference: **WP22A planning correction / PR #329**

## Symptom / failing gate

The public/free/multi-user hosted-runtime planning correction updated the intended V10 authority from a PROJECT-OWNER/home-Lenovo final runtime to a managed-cloud/no-home public target, but successive exact-head CI cycles exposed stale consumers of the old authority:

- WP17 source-gate markers still expected the old OWNER-only WP22A wording;
- the WP22A workflow still treated Cloudflare Access + Tunnel + Lenovo loopback as selected final architecture instead of dormant Phase-A provenance;
- Engineering Governance documentation checks still assumed the pre-amendment runtime-hosting status;
- the full authoritative Regression Shield still contained tests requiring Personal Node as `v10_primary_host`, an absolute `Render.com not V10 hosting target` message and other pre-amendment text markers;
- Copilot live guidance had accidentally dropped the protected V9 `v9.0.0` effective-production/controlled-maintenance marker while being rewritten for V10.

## Root cause

The architecture correction was initially propagated by document category rather than by **authority-consumer graph**. Human-facing planning documents and new machine contracts were updated first, while inherited tests/workflows/navigation guards that encoded the old architecture were discovered incrementally by expensive CI.

## Blast radius searched

The correction was expanded across:

- V10 live guidance and protected V9 navigation markers;
- Engineering Quality machine contract and validator;
- documentation-consistency validator;
- WP17 Web/security source gate;
- WP22A service-selection/execution contracts;
- WP22A workflow source-contract assertions and dormant Phase-A IaC checks;
- public-product plan regressions;
- engineering-governance regressions;
- full authoritative Regression Shield;
- provider/public-ingress activation semantics.

No runtime feature implementation, provider apply, broker authority or public exposure is authorized by these planning corrections.

## Why preflight missed it

Preflight searched direct references to the new amendments and major current-WP documents, but did not initially enumerate every executable test/workflow that treated old documentation strings or old JSON keys as architecture truth. Fragile whole-text assertions allowed stale implementation assumptions to survive after their owning authority had been superseded.

## Corrective change

- make the public hosted runtime contract the machine source for no-home, browser/Internet-only, free-launch and tenant-scoped broker ownership invariants;
- keep Cloudflare/Lenovo Phase-A source only as explicitly dormant historical safety provenance until the corrected provider-selection gate chooses the final architecture;
- update WP17/WP22A/governance consumers to test the **property** being protected rather than obsolete provider/topology wording;
- preserve the protected V9 `v9.0.0 -> app:app` effective production/recovery baseline in live engineering guidance;
- replace Personal-Node-final regression tests with managed-cloud/no-home negative tests;
- keep provider choice unselected: Render, Cloudflare or another provider is neither silently selected nor permanently forbidden by a stale historical assertion.

## Permanent regression/guard

The branch now requires machine-checked invariants for:

- managed-cloud public origin;
- no OWNER home IP/Wi-Fi/router/LAN/Lenovo availability dependency;
- Internet required for registration/login/product use and no offline authenticated product mode;
- no native client required for ordinary USER access;
- PROJECT OWNER not being a special product role;
- tenant scope coming only from server-side session authority;
- tenant-owned READ/optional TRADE credentials with no global/shared credential;
- free initial launch flags disabled for billing/trial/subscription/premium gating;
- `PUBLIC_MULTI_USER_ENABLED=false` until corrected exit gates pass;
- source-marker presence never implying live ingress or provider activation;
- protected V9 `app:app` rollback/effective-production baseline remaining visible.

## Future prevention rule

Before an architecture amendment is considered pre-CI ready, build an explicit authority-consumer inventory:

`authority docs -> machine contracts -> validators -> workflows -> focused tests -> full Regression Shield -> live guidance -> historical lessons with supersession notes`.

Search by **old semantic properties and old key names**, not only by new amendment filenames. A later OWNER-approved amendment supersedes conflicting historical lessons; historical entries remain provenance and must never be interpreted as current architecture authority.

## Dependency/tooling knowledge change

Provider-neutral security properties are more durable than provider-specific strings. CI should distinguish three states explicitly:

1. historical/dormant source that must remain syntactically safe;
2. selected implementation authority;
3. live activated production state.

Presence of source for state 1 must never be accepted as proof of states 2 or 3.
