# ADR-0010 — Omni-CIO account identity, multi-tenant isolation and Web authentication

Status: **OWNER APPROVED / PROPOSED FOR PROGRAM ACCEPTANCE**  
Date: **2026-08-10**

## Context

The accepted V10 baseline deliberately implemented OWNER-only Personal semantics while making WP12/WP13 tenant-ready. During WP15 OWNER acceptance, the OWNER clarified the intended product account model:

- the user registers/signs in to Omni-CIO through Telegram or VK ID;
- the Omni-CIO account persists independently of a phone/browser;
- multiple external login identities may be linked to one internal account;
- each user sees only their own investment/private state;
- broker credentials are entered through the Web product, not through ordinary PowerShell UX;
- one tenant may have multiple T-Invest accounts/connections;
- READ and optional TRADE credentials are distinct and must be identity-matched to the same verified broker account before execution;
- future public users must remain strictly isolated.

The existing Personal V10 architecture also has a zero-custody/private-data boundary and explicit broker/legal gates that prohibit treating the change as permission to build a centralized public T-Invest-data SaaS.

## Decision

Adopt a split-plane identity architecture:

1. A minimal central **Account/Identity Plane** owns internal Omni-CIO user identity, external Telegram/VK bindings, server-side sessions, recovery/security state, license/commercial state and approved private-node routing.
2. Each internal user owns exactly one isolated tenant in the baseline model.
3. Investment-private data remains in the user's approved **Private Data Plane** by default; browser/phone is never authoritative storage.
4. Telegram and VK ID are authentication providers, not primary business identifiers.
5. Ordinary authentication has no Omni-CIO password. Sessions are server-side and revocable.
6. Broker credentials are tenant-owned `BrokerConnection` secrets provisioned via authenticated Web settings. Raw credentials are never returned to the browser.
7. READ and TRADE credential bindings are independent; execution for an account requires an exact verified identity intersection.
8. Public multi-user activation is feature-gated off until security, tenant-isolation, broker-contract, capacity and legal gates pass.

## Alternatives considered

### A. Keep one OWNER/global machine account

Rejected for the target product because it cannot support durable user identity, account recovery or future isolated users without a later breaking rewrite.

### B. Store all user portfolio data and broker tokens in one central SaaS database

Rejected as the default because it conflicts with the accepted zero-custody/private-state design and current T-Invest public-service/retransmission restrictions. It would require separate broker/legal/privacy approval.

### C. Put authoritative account/private state in the user's phone/browser

Rejected because loss/replacement of the device would threaten continuity, background monitoring would stop with the device, and browser storage is not an acceptable secret/session authority.

### D. Create local Omni-CIO passwords

Rejected for ordinary login because Telegram and VK ID provide the approved low-friction identity proof and a local password database adds credential-reset/attack surface without product value. Emergency recovery remains a separate high-entropy mechanism.

## Consequences

Positive:

- stable internal identity independent of social provider and client device;
- clear tenant isolation boundary for API/DB/jobs/cache/AI;
- safe multiple-account broker model;
- normal Web-only broker credential UX;
- future scalability without making the browser or GitHub authoritative;
- preserves Personal/zero-custody private-data direction.

Costs/risks:

- WP12/WP13 OWNER-only constraints eventually require forward migrations and stronger row-level isolation;
- authentication/session/recovery becomes a first-class security subsystem;
- central identity plane creates personal-data/legal obligations that must be inventoried and reviewed;
- public multi-user activation cannot occur under the current T-Invest public API terms without a compatible architecture/permission determination;
- provider outages require explicit degraded login/session behavior.

## Rollback

Before public multi-user activation, the safe rollback is to keep `PUBLIC_MULTI_USER_ENABLED=false` and retain OWNER/test-only account access. Existing V9 rollback and V10 real-trading kill switches are unchanged.

## Related authority

- `docs/master-plan/OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md`
- `docs/master-plan/OMNI_CIO_V10_AUTONOMOUS_PORTFOLIO_GOVERNANCE_AND_COMMERCIAL_MODEL_AMENDMENT.md`
- `docs/architecture/V10_ZERO_CUSTODY_LICENSE_UPDATE_CONTRACT.json`
- `docs/legal/V10_RU_COMMERCIAL_LEGAL_GATES.md`
