# Omni-CIO V10 — Live User Operability Acceptance Standard

Status: **AMENDMENT-13 GOVERNANCE STANDARD — EFFECTIVE WITH ACCEPTED AMENDMENT 13**

This standard defines the evidence required when a user-facing capability moves from implementation-only state to `LIVE_OPERABLE`, and the additional boundary for `REAL_MONEY_AUTHORIZED`.

It does not replace `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`, the Work Package template, Amendment 12, security architecture, provider-specific gates or broker/legal evidence.

## 1. Canonical product boundary

Live acceptance targets the one canonical Omni-CIO Web. A separate staging website is not required.

The ordinary product path must be the same path supported users actually use:

`ordinary browser -> canonical Omni-CIO Web -> Telegram/VK product authentication -> OmniCIOUserAccount -> Tenant -> server-side Session -> accepted capability`

Engineering/OWNER/provider identities must not mint a product session or select a tenant.

## 2. `LIVE_OPERABLE` acceptance checklist

A capability may transition to `LIVE_OPERABLE` only when every directly applicable item below has real evidence:

- implementation/technical Exit Gate accepted;
- exact-head applicable verification concluded `success`;
- accepted deployment/release is present on the canonical serving boundary;
- ordinary USER path works without demo/preview/admin bypass;
- real-user operability is proven with the minimum safe non-secret result;
- tenant authority is derived server-side;
- deterministic cross-tenant negative tests pass when multi-user state is involved;
- controlled real-user multi-tenant acceptance is performed when required by the owning gate without exposing another tenant's private data;
- secret/private payload exclusion is verified;
- health/monitoring/degraded behavior is defined;
- rollback/recovery is defined and tested as required;
- capacity/rate/abuse controls are accepted where applicable;
- external provider, broker, privacy/legal or secret-custody evidence exists where applicable;
- capability ledger transition records evidence references and any emergency control;
- no unresolved blocking security/recovery finding remains.

Synthetic/provider-double evidence may support technical verification but may not be presented as real external/provider/legal acceptance.

## 3. Multi-user isolation acceptance

For any capability that reads, writes, caches, schedules, exports, restores or otherwise processes tenant-private state, acceptance must prove:

- USER A cannot read or mutate USER B state by object ID, URL, request body, headers or cache keys;
- jobs/queues carry immutable tenant scope;
- PostgreSQL/RLS or the accepted durable-store equivalent independently enforces tenant scope where required;
- stale/revoked sessions cannot retain authority;
- restore/recovery preserves tenant isolation;
- logs, telemetry and evidence remain sanitized;
- broker credentials and raw provider credentials are inaccessible across tenants.

Real-user acceptance complements but never replaces deterministic cross-tenant negative tests.

## 4. External-evidence rule

A capability remains `BLOCKED_EXTERNAL` when an applicable external fact lacks accepted evidence, including provider configuration, broker terms/permission, secret custody, privacy/personal-data, legal/regulatory, production capacity/operations or recurring-cost authority.

Engineering must not infer approval from technical API support. A user-supplied credential does not waive provider/broker terms.

## 5. Broker READ acceptance

T-Invest READ live operability requires the owning accepted evidence for broker terms/permission, tenant-scoped encrypted secret custody, production security/privacy/legal and connector behavior.

The accepted result may expose only that USER's verified accounts and reviewed read-side data. READ never uses TRADE/full-access authority as fallback.

## 6. TRADE credential provisioning acceptance

A TRADE credential provisioning capability may become `LIVE_OPERABLE` before Real submission only when:

- authenticated Web provisioning/replace/revoke flow is accepted;
- raw credential is never returned or stored in browser Web Storage;
- tenant-scoped secret custody is accepted;
- verified TRADE accounts are discovered independently;
- `VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS` is enforced;
- mismatch fails closed;
- UI explicitly states that connected/verified TRADE credential does not authorize Real broker submit.

## 7. `REAL_MONEY_AUTHORIZED` acceptance

Only the actual reviewed broker-submit capability may use `REAL_MONEY_AUTHORIZED`.

In addition to all applicable live-operability requirements, evidence must prove Sandbox/Shadow requirements, immutable plan approval, authenticated USER approval, fresh preflight, account intersection, own-cash/own-position constraints, drift stop/re-plan, idempotency, ambiguous-submit reconciliation, broker reconciliation, durable audit and independent kill switches.

Transfer/withdrawal/margin/leverage/uncovered-short authority is not implied.

## 8. Evidence hygiene

Acceptance evidence may record sanitized run IDs, release SHAs, provider object IDs that are not secrets, masked identities, pass/fail summaries, timestamps and approved public URLs.

Never record raw provider/broker secrets, Authorization headers, session tokens, auth codes, PKCE verifiers, full broker account identifiers, private portfolio payloads, DB passwords or encryption keys in GitHub, CI, screenshots, artifacts or chat.

## 9. Emergency disablement

Emergency kill switches are operational controls separate from capability lifecycle state. An incident may temporarily disable a capability while the accepted lifecycle state remains historically recorded.

The dashboard/ledger must record the emergency-control condition without falsely claiming that the capability's original acceptance evidence disappeared.

## 10. Acceptance result

The final result is binary for the proposed transition:

- `LIVE_OPERABLE` / `REAL_MONEY_AUTHORIZED` only with all direct applicable evidence; or
- `BLOCKED_EXTERNAL` / remain `IMPLEMENTED` with precise blocker(s).

There is no “mostly live” or “legal probably fine” acceptance state.
