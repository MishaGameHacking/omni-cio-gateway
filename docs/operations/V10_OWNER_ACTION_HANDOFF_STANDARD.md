# Omni-CIO V10 — OWNER Action Handoff & Runtime Standard

Status: **OWNER-APPROVED POLICY / PUBLIC-HOSTED RUNTIME UPDATE EFFECTIVE ON MERGE**  
Original policy date: 2026-08-16  
Runtime-hosting update: 2026-08-18  
Scope: every engineering/operations handoff that asks the PROJECT OWNER to perform an action outside autonomous GitHub/code/CI execution.

## 1. Purpose

This standard prevents ambiguous OWNER instructions and prevents accidental drift between engineering/recovery infrastructure and the final public-production runtime.

The OWNER is not expected to search through provider dashboards, infer the right account/workspace, guess which button is safe, or discover the required page independently. Engineering must do that work first.

The PROJECT OWNER is also not a special Omni-CIO product user. Product acceptance uses the same ordinary USER account/tenant/session path intended for supported users.

## 2. Direct-link-first law

Before asking the OWNER to perform any external website, account, billing, consent, provider, GitHub, Cloudflare, broker, domain or other browser action, engineering must include a **direct official HTTPS link to the exact stable page when such a stable official link exists**.

A generic instruction such as `open Settings`, `go to Billing`, `find Zero Trust`, `open the provider dashboard`, or `check your account` is not sufficient by itself.

If an exact deep link is not stable, safe to disclose, or verifiable from current official sources, engineering must:

1. say explicitly that no stable exact deep link could be verified;
2. provide the closest verified official starting URL;
3. provide the exact verified click path from that page;
4. describe the page title/control text the OWNER should see before continuing;
5. stop if the observed UI differs materially.

Never provide shortened links, third-party redirectors, secret-bearing URLs, sensitive login continuation URLs or private runtime URLs that the OWNER was instructed not to disclose.

## 3. Mandatory OWNER handoff format

Every OWNER-only instruction must contain all applicable fields before the OWNER is asked to act:

- **Why this is required:** exact non-delegable prerequisite or acceptance boundary;
- **Direct official link:** exact stable HTTPS page, or closest verified official start page with the explicit reason a deeper stable link is unavailable;
- **Scope:** exact account/repository/workspace/service/device being changed;
- **Action:** one bounded set of clicks or one reviewed idempotent command/block;
- **Expected result:** exact page state, label, PASS line or non-secret result that proves success;
- **STOP conditions:** what unexpected screen/error/state means stop without improvising;
- **Do not do:** adjacent destructive, billable, premature-public, secret-disclosure, duplicate-resource or authority-expanding actions that must not be taken;
- **Safe return:** the minimum non-secret result to send back to engineering.

Instructions must be executable by a non-developer OWNER without guessing.

## 4. Current-source verification law

Provider dashboards, pricing, terms and navigation can change. Before giving click instructions whose UI or consequences may have changed, engineering must verify current official provider documentation/current official service surface.

Do not reuse stale navigation/pricing/eligibility merely because it worked earlier.

For billing, payment, domain purchase, paid plan activation, credential scopes, public exposure, account deletion, irreversible provider mutation or security-sensitive consent, state exact cost/authority consequence **before** OWNER confirmation.

## 5. One bounded OWNER action at a time

Do not combine unrelated manual work merely because the OWNER is available.

Ask only for the first genuinely non-delegable prerequisite. After its safe result is returned, resume autonomous work and ask again only if another true OWNER-only boundary is reached.

Routine code changes, CI debugging, log inspection, PR housekeeping, IaC preparation, documentation, testing and provider/API automation remain engineering work.

## 6. V10 local runtime / rendering law — superseded for public production

The earlier rule that V10 Web/API/private state must be rendered and served on the Lenovo/replacement Personal Node is **superseded for final public production** by the OWNER-approved Public Free Multi-User Hosted Runtime amendment.

Current binding separation:

- Lenovo remains engineering, authoritative self-hosted CI, controlled acceptance, recovery rehearsal and protected rollback;
- an explicitly reviewed non-production local/staging runtime may still run on Lenovo;
- ordinary public USER availability must not depend on PROJECT OWNER home public IP, Wi-Fi/router/LAN, home Internet/power or Lenovo;
- final public Web/API and required hosted tenant-private state use an approved managed-cloud production runtime selected through the owning WP22A service/security/recovery gate;
- cloud/provider selection is **not** permission to create a competing Web/Core stack;
- hosted tenant-private state and encrypted broker credentials require the exact security/privacy/personal-data/legal/broker/recovery gates in the active amendments.

No provider purchase or production activation is implied by this policy update.

## 7. Render.com boundary

The existing Render.com `app:app` service remains only the protected V9 production/recovery baseline until its responsible V10 cutover/decommission gate.

Do not treat that protected V9 service, or an empty/new Render workspace, as automatically selected V10 public production.

For future V10 public hosting:

- Render.com is neither selected nor forbidden merely by brand name;
- any candidate provider, including Render if reconsidered, must pass the same current managed-cloud service-selection/security/recovery/cost/legal gate;
- do not create/purchase/mutate a new V10 service before the source-controlled architecture and OWNER-required budget/provider decision are accepted;
- do not mutate/remove the protected V9 `app:app` baseline merely because V10 later gets a cloud runtime.

## 8. External-access implication

The corrected WP22A provider architecture must preserve:

- public HTTPS/TLS/Host/proxy security;
- product authentication independent of provider membership;
- server-side USER sessions and tenant isolation;
- no global/shared USER broker credential;
- no broker-write authority expansion;
- source-controlled configuration/deployment/recovery;
- managed-cloud production availability independent of OWNER home infrastructure;
- fail-closed T-Invest public connector until broker terms/permission are accepted.

Cloudflare may be edge/DNS/TLS/WAF/DDoS/origin-protection infrastructure. A Cloudflare Tunnel whose sole production origin is OWNER home Lenovo does not satisfy the final public-production requirement.

## 9. Safety invariants

This standard does not change:

- protected V9 `app:app` compatibility/recovery;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- tenant-scoped READ/optional TRADE separation;
- no transfer/withdrawal authority;
- GitHub as engineering source of truth;
- source / tenant-private durable state / runtime-secret separation;
- Master Plan ordering and Exit Gates;
- all-applicable-exact-head SUCCESS-only merge law.

## 10. Enforcement

This standard is a required governance source after acceptance. Engineering-governance/public-product guards must fail if direct-link-first handoff, no-home public-production separation, protected V9 Render boundary, OWNER budget discipline or product USER/engineering authority separation is removed or weakened.

Machine-readable invariant: `owner_must_not_be_required_to_discover_target_page=true`.
