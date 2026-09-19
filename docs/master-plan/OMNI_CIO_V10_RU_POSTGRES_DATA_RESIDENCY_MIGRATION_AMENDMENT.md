# Omni-CIO V10 — Russian PostgreSQL Data-Residency Migration Authority / Amendment 17

**Status:** OWNER-APPROVED / EFFECTIVE ONLY WHEN ACCEPTED ON PROTECTED main  
**OWNER decision:** 2026-09-19  
**Scope:** production PostgreSQL provider/data-residency migration required before Russian public-user activation  
**Product progress effect:** NONE by itself  
**Runtime mutation effect:** NONE by itself  
**Owning dashboard:** issue #559

## 1. Purpose

Omni-CIO keeps its accepted PostgreSQL 18, migrations, tenant model, RLS/FORCE RLS, server-side session and recovery semantics. The project must not discard that work merely because the current active provider-specific production bootstrap is Neon/Frankfurt.

The OWNER approved a reuse-first migration direction:

PostgreSQL 18 application contract -> provider adapter -> Russian-hosted managed PostgreSQL 18.

The first candidate for equivalent-provider proof is **Timeweb Cloud Managed PostgreSQL 18** in a Russian region, with Moscow preferred for the first synthetic proof.

This amendment does not self-certify 152-FZ compliance. It establishes a conservative engineering launch boundary while the repository legal gate remains fail-closed: real Russian public-user personal data must not be introduced into a non-Russian primary database before the final qualified legal/data-flow determination is accepted.

## 2. Authority and precedence

Amendments 12, 13, 14, 15 and 16 remain active.

Amendments 14/15 already require accepted Neon/PostgreSQL authority to remain intact until an explicit equivalent migration proof exists. Amendment 17 supplies the governance and compatibility sequence for that proof.

Where current Cloudflare/Neon implementation wording assumes Neon is the permanent future production database provider, Amendment 17 supersedes only that provider permanence assumption. It does not erase historical Neon evidence or weaken PostgreSQL/RLS/recovery requirements.

Cloudflare Workers Paid remains the selected public application/edge/build platform. This amendment changes only the future PostgreSQL provider authority after parity/cutover acceptance.

## 3. Root cause and blast radius

The application persistence layer is predominantly provider-neutral PostgreSQL:

- PostgreSQL 18 schema/migrations;
- psycopg connection semantics;
- USER/Tenant/session/identity tables;
- RLS/FORCE RLS;
- logical pg_dump / pg_restore recovery.

The accepted Cloudflare database provisioning/release layer is provider-specific:

- Neon API organization/project/branch authority;
- Neon Frankfurt region and host suffix checks;
- Neon connection-URI derivation;
- Neon Function/OIDC bootstrap transport;
- Neon project/branch custody and recovery paths;
- provider-specific secret names/workflow gates.

Therefore a safe migration wraps/replaces provider infrastructure while preserving application/database truth.

## 4. Reuse decisions

### REUSE_AS_IS

- PostgreSQL major 18;
- migration history and checksum identity;
- SQL schema and constraints;
- tenant scope semantics;
- RLS/FORCE RLS policies;
- psycopg application access;
- server-side session/account/identity model;
- logical backup/restore contract;
- cross-tenant negative tests.

### WRAP_ADAPTER

- provider provisioning;
- database/user creation;
- runtime DSN generation and custody;
- provider region/location verification;
- Cloudflare -> PostgreSQL TLS connectivity;
- provider health/readiness;
- provider-native physical backup integration.

### RETIRE only after accepted cutover

- active Neon production management/bootstrap authority;
- Neon-specific production recovery mutation path.

Historical Neon evidence remains historical. Neon may remain development/synthetic-only after cutover only when no real Russian user personal/private data is present.

## 5. Candidate provider facts — mutable and revalidated

Official Timeweb Cloud documentation revalidated on 2026-09-19 states:

- Managed PostgreSQL supports PostgreSQL 18;
- Russian regions include Moscow and Saint Petersburg;
- public database connectivity can use TLS;
- Terraform/API/CLI automation is available;
- PostgreSQL privileges include CREATE_ROLE;
- documented role management supports CREATE ROLE, membership and ALTER DEFAULT PRIVILEGES;
- the minimum 1 CPU / 1 GB RAM / 8 GB NVMe tariff does not support creating additional database users.

External facts are mutable and must be revalidated before provider purchase or mutation.

Canonical references:

- https://timeweb.cloud/services/postgresql
- https://timeweb.cloud/docs/dbaas/postgresql
- https://timeweb.cloud/docs/dbaas/postgresql/users-and-privileges
- https://timeweb.cloud/docs/dbaas/postgresql/roles
- https://timeweb.cloud/docs/dbaas/postgresql/connect-to-database
- https://timeweb.cloud/docs/dbaas/dbaas-create
- https://timeweb.cloud/docs/terraform
- https://timeweb.cloud/docs/zony-dostupnosti/servisy-i-zony-dostupnosti

## 6. Non-negotiable PostgreSQL parity

A candidate is rejected unless synthetic proof establishes all of the following on PostgreSQL 18:

1. separate bootstrap/admin and runtime identities;
2. runtime login is LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
3. runtime role cannot inherit from or SET ROLE to broader authority;
4. runtime role owns neither database, application schema nor application objects;
5. current migrations apply in accepted order;
6. current schema/migration state is exact;
7. grants/revokes and ALTER DEFAULT PRIVILEGES semantics are sufficient;
8. ENABLE ROW LEVEL SECURITY and FORCE ROW LEVEL SECURITY work exactly as required;
9. unscoped and cross-tenant negatives remain fail-closed;
10. current backup/restore and restore-isolation checks remain valid.

Provider convenience roles or broad default roles must not substitute for the accepted least-privilege runtime contract.

## 7. Minimum-tier cost rule

The documented minimum Timeweb tariff is **not accepted for Omni-CIO production merely because it is cheapest**.

Because Omni-CIO requires a separate least-privilege runtime login, the minimum tier remains rejected until a real synthetic provider proof demonstrates that the required separate identities and role semantics are supported without weakening security.

If the minimum tier cannot satisfy that requirement, select the cheapest Timeweb configuration that does. Do not collapse bootstrap and runtime authority to reduce cost.

Automatic scaling, replicas, paid add-ons or higher spend are not authorized by this amendment. Any material recurring-cost increase requires fresh OWNER approval before provider mutation.

## 8. Network/TLS boundary

Initial compatibility target is direct Cloudflare Container -> PostgreSQL over the standard PostgreSQL protocol.

Required:

- TLS enabled;
- certificate validation enabled;
- hostname verification enabled where the provider certificate model permits;
- no sslmode=disable, insecure CA bypass or plaintext credential transport;
- runtime DSN remains secret custody, never repository content;
- provider management credentials remain outside runtime application authority;
- public-IP exposure, if required for Cloudflare connectivity, is accepted only after the owning network/security gate.

Hyperdrive is not assumed and is not required for this migration proof.

## 9. Recovery boundary

Timeweb provider-native physical backups are additive defense only.

The accepted Omni-CIO logical recovery contract remains:

- PostgreSQL 18;
- pg_dump --format=custom --no-owner --no-privileges;
- pg_restore;
- integrity hash/size checks;
- restore to a separate database;
- migration/schema/tenant-boundary revalidation;
- cross-tenant negative rehearsal;
- no secret/private payload in GitHub or CI artifacts.

Provider backup success alone never proves Omni-CIO recovery parity.

## 10. Data boundary before cutover

Before RU-PG-D production cutover:

- compatibility tests use synthetic data only;
- no real Telegram user, consent, session, account, tenant, portfolio or broker payload is copied to the candidate;
- PUBLIC_MULTI_USER_ENABLED=false;
- OMNI_V10_TELEGRAM_LOGIN_ENABLED=false;
- OMNI_V10_VK_ID_LOGIN_ENABLED=false.

The current accepted Neon production database authority remains untouched until equivalent migration/cutover evidence is accepted. This is a continuity boundary, not permission to activate real users on Neon.

## 11. Mandatory split sequence

DB/provider authority and production cutover are Amendment-12 mandatory split boundaries.

The migration therefore executes as:

1. **RU-PG-A — authority + source compatibility contract** — governance/source only; no Timeweb purchase/mutation; no database/runtime secret change.
2. **RU-PG-B — provider bootstrap + synthetic PostgreSQL 18 parity** — real Timeweb provider action; synthetic data only; exact role/migration/RLS proof.
3. **RU-PG-C — Cloudflare TLS/runtime + recovery parity** — synthetic/staging only; direct connectivity, secret custody, backup/restore and failure-mode proof.
4. **RU-PG-D — production database cutover** — only after qualified legal/privacy/data-flow and security acceptance; no public-user activation is implied by database cutover.
5. **RU-PG-E — Neon production-authority retirement + closeout** — remove active Neon production management/recovery coupling only after accepted cutover; preserve historical evidence.

Every published checkpoint must become CERTIFIED_GREEN before the next stage.

## 12. Legal gate remains external

Engineering does not claim that selecting a Russian data-center provider alone completes 152-FZ compliance.

The existing personal-data/operator/localization/cross-border/retention/security and final legal-signoff gates remain required for the actual launch model.

## 13. Protected invariants

This amendment does not change protected V9 app:app; one canonical product line; GitHub rank-1 engineering authority; Cloudflare application/edge/build authority; PostgreSQL 18 tenant/RLS truth; secret/private-data exclusion; public-user/Telegram/VK fail-closed flags; broker-write/Real-money locks; WP23+ lock; or WEB-VISUAL OWNER START lock.

## 14. RU-PG-A acceptance gate

Amendment 17 becomes active only after this focused governance checkpoint passes deterministic guards, all applicable exact-head CI/Sonar/review, squash merge, exact-new-main Regression Shield and V10 Engineering Governance.

Only then may RU-PG-B provider bootstrap begin.
