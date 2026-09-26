# Omni-CIO V10 — Timeweb No-OWNER-Laptop Manual Dependency Amendment

Status: **OWNER-APPROVED / ACTIVE FOR TIMEWEB CONSOLIDATION**
Decision date: **2026-09-23**
Owning System Update: **TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED**

## 1. OWNER decision

For the Timeweb production path, normal engineering continuation must not require the
PROJECT OWNER to open an Administrator shell on the personal Lenovo/laptop, repair a
Git safe-directory state, or manually regenerate machine-local ACL evidence merely to
advance a GitHub PR.

The active product/runtime direction remains:

`ChatGPT + GitHub + Timeweb Cloud + Telegram Login`

Telegram Login authenticates the human Telegram USER account. The future Telegram bot
remains a separate WP23+ post-auth companion capability.

## 2. Superseded current blocker

The WP17 Windows READ-vault evidence gate remains valid historical/local-node security
evidence, but it is **not** a current Timeweb production secret-custody dependency.

For the Timeweb branch:

- `omni_cio/web/broker_vault_v1.py` and its Windows DPAPI/ACL machinery are
  historical/local-only;
- current Timeweb runtime source must not import or instantiate that Windows vault;
- the old OWNER/Admin exact-head ACL evidence must not block Timeweb source/runtime
  consolidation;
- the historical local-vault audit is preserved as manual evidence and is not deleted;
- no broker credential, ciphertext, token or private payload is copied to GitHub to
  replace that evidence.

## 3. Replacement security boundary

This amendment does **not** weaken broker-secret security.

Until a hosted tenant-secret backend is accepted:

- Timeweb hosted broker credential mutation remains fail-closed;
- current hosted routes may not accept/store/replace/revoke live broker credentials;
- no global/shared T-Invest READ or TRADE token is allowed;
- `omni_cio/web/hosted_secret_custody_v1.py` remains the provider-neutral hosted
  custody contract;
- future hosted custody must be tenant-scoped, encrypted at rest, unavailable to the
  browser/ordinary CI/unrelated tenants, and backed by an accepted Timeweb/PostgreSQL
  security design;
- broker-write and Real-money authority remain independently gated.

The required PR check formerly named
`OWNER read-vault and runner-isolation evidence` is retained for branch-protection
continuity, but its current Timeweb meaning is a deterministic source-security audit:
it proves the deployed Timeweb composition has no Windows local-vault dependency and
that broker mutation remains fail-closed until hosted custody is accepted.

## 4. Historical evidence retention

The original Windows provision/finalize/audit scripts remain archive-in-place for:

- historical accepted evidence;
- local/recovery investigation if later needed;
- regression comparison.

They are not current Timeweb deployment authority and are not automatically executed
on pull requests.

## 5. No authority expansion

This amendment does not:

- authorize TW-C provider mutation before TW-B GREEN/acceptance;
- authorize production PostgreSQL cutover;
- authorize `omnicio.ru` DNS/TLS cutover;
- activate public Telegram registration;
- authorize broker write, `REAL_TRADING_ENABLED=true`, transfer/withdrawal, margin,
  leverage or uncovered short;
- start WEB-VISUAL or WP23+.

All existing exact-head, tenant-isolation, RLS/FORCE-RLS, recovery, secret-exclusion,
review and SUCCESS-only merge laws remain active.
