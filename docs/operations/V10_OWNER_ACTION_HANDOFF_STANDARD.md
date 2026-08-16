# Omni-CIO V10 — OWNER Action Handoff & Local Runtime Standard

Status: **OWNER-APPROVED POLICY / EFFECTIVE ONLY AFTER GOVERNANCE MERGE TO `main`**  
Date: 2026-08-16  
Scope: every future engineering/operations handoff that asks the OWNER to perform an action outside autonomous GitHub/code/CI execution.

## 1. Purpose

This standard prevents ambiguous OWNER instructions and prevents accidental drift from the accepted Personal-Node runtime model.

The OWNER is not expected to search through provider dashboards, infer the right account/workspace, guess which button is safe, or discover the required page independently. Engineering must do that work first.

## 2. Direct-link-first law

Before asking the OWNER to perform any external website, account, billing, consent, provider, GitHub, Cloudflare, broker, domain, or other browser action, the engineering response must include a **direct official HTTPS link to the exact stable page when such a stable official link exists**.

A generic instruction such as `open Settings`, `go to Billing`, `find Zero Trust`, `open the provider dashboard`, or `check your account` is not sufficient by itself.

If an exact deep link is not stable, not safe to disclose, or cannot be verified from current official sources, engineering must:

1. say explicitly that no stable exact deep link could be verified;
2. provide the closest verified official starting URL;
3. provide the exact verified click path from that page;
4. describe the page title/control text the OWNER should see before continuing;
5. stop if the observed UI differs materially.

Never provide shortened links, third-party redirectors, secret-bearing URLs, login continuation URLs containing sensitive parameters, or private runtime URLs that the OWNER was instructed not to disclose.

## 3. Mandatory OWNER handoff format

Every OWNER-only instruction must contain all applicable fields below before the OWNER is asked to act:

- **Why this is required:** the exact non-delegable prerequisite or acceptance boundary;
- **Direct official link:** exact stable HTTPS page, or the closest verified official start page with the explicit reason a deeper stable link is unavailable;
- **Scope:** exact account/repository/workspace/service/device being changed;
- **Action:** one bounded set of clicks or one reviewed idempotent command/block;
- **Expected result:** exact page state, label, PASS line, or non-secret result that proves success;
- **STOP conditions:** what unexpected screen/error/state means the OWNER must stop without improvising;
- **Do not do:** adjacent destructive, billable, public-ingress, secret-disclosure, duplicate-resource, or authority-expanding actions that must not be taken;
- **Safe return:** the minimum non-secret result to send back to engineering.

Instructions must be written so that a non-developer OWNER can execute them without guessing.

## 4. Current-source verification law

Provider dashboards and navigation can change. Before giving click instructions whose UI may have changed, engineering must verify the current official provider documentation or current official service surface.

Do not reuse a stale navigation path merely because it worked in an earlier chat.

For billing, payment, domain purchase, paid plan activation, credential scopes, public exposure, account deletion, irreversible provider mutation, or security-sensitive consent, the exact cost/authority consequence must be stated **before** the OWNER confirms the action.

## 5. One bounded OWNER action at a time

Do not combine unrelated manual work into a long checklist merely because the OWNER is available.

Ask only for the first genuinely non-delegable prerequisite. After its safe result is returned, engineering resumes autonomous work and asks again only if another true OWNER-only boundary is reached.

Routine code changes, CI debugging, log inspection, GitHub PR housekeeping, Terraform preparation, documentation, testing, and provider/API automation remain engineering work.

## 6. V10 local runtime / rendering law

The OWNER clarified that the V10 Web/product runtime is **rendered, built and served on the approved Lenovo/replacement Personal Node using the source-controlled Omni-CIO repository**, without requiring a separate paid cloud Web-hosting service for normal V10 operation.

For V10:

- the Personal Node is the primary Web/API/runtime host;
- `apps/web` and related source-controlled assets are built/rendered on the Personal Node according to the owning V10 deployment contract;
- private portfolio state, broker credentials, private history and runtime secrets remain on the approved private Data Plane and are not moved to a cloud hosting service merely for convenience;
- browser-only external access may use a reviewed access/tunnel provider such as the WP22A-selected candidate, but that provider is an access/security transport in front of the Personal Node, **not the authoritative V10 application host or private-state store**;
- the V10 Definition of Done must not depend on paying Render.com or another general-purpose cloud application host unless a later OWNER-approved amendment proves that the Personal-Node model cannot satisfy the owning requirement.

## 7. Render.com boundary

Do not confuse **local rendering/serving on the Lenovo Personal Node** with the commercial service **Render.com**.

The existing Render.com `app:app` service is retained only as the protected V9 production/recovery baseline until the responsible V10 parity/decommission gate changes that accepted state.

For V10 feature work:

- do not create a new Render.com Web Service, worker, PostgreSQL instance, deployment target, or paid plan as the normal V10 runtime;
- do not treat an empty/new Render.com workspace as Omni-CIO authority or as a replacement for the accepted V9 service;
- do not ask the OWNER to configure or pay Render.com for V10 unless a future OWNER-approved amendment explicitly authorizes it;
- do not remove or mutate the protected V9 Render baseline merely because V10 is self-hosted on the Personal Node.

## 8. External-access implication

A browser-access provider chosen by WP22A must terminate/mediate access to the reviewed Personal-Node origin while preserving:

- loopback/private-origin protection;
- authenticated OWNER-only access until later public/multi-user gates are explicitly accepted;
- no broker-write authority expansion;
- no public unauthenticated ingress;
- source-controlled configuration and recoverability;
- local operation/recovery when the external-access provider is unavailable where the owning contract permits.

The provider must not silently become a second application/control plane.

## 9. Safety invariants

This standard does not change:

- protected V9 `app:app` compatibility/recovery;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- READ/Sandbox/TRADE credential separation;
- no transfer/withdrawal authority;
- GitHub as engineering source of truth;
- private durable state / source / runtime-secret separation;
- Master Plan WP ordering and Exit Gates.

## 10. Enforcement

This standard is a required governance source after acceptance. The engineering-governance validator and regression tests must fail if the direct-link-first OWNER handoff or local-runtime/Render boundary is removed or weakened.

Machine-readable invariant: `owner_must_not_be_required_to_discover_target_page=true`.
