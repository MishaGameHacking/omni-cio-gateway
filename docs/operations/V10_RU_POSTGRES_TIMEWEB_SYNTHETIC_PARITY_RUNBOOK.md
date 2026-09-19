# V10 RU-PG-B — Timeweb PostgreSQL 18 Synthetic Parity Runbook

Status: **SOURCE READY / REAL PROVIDER EVIDENCE PENDING**

Owning issue: #559  
Accepted prerequisite: Amendment 17 / RU-PG-A on protected main through PR #560 and Production Release #86.

## Purpose

RU-PG-B proves that a real Timeweb Cloud Managed PostgreSQL 18 cluster in Moscow can satisfy the existing Omni-CIO PostgreSQL contract without weakening roles, RLS, migrations or secret custody.

This stage is synthetic only. It must not receive real personal data, Telegram identities, real sessions, real portfolio data, broker credentials or production secrets.

Official Timeweb facts revalidated on 2026-09-19:

- PostgreSQL 18 is available;
- DBaaS is available in Moscow MSK-1, Terraform location ru-3;
- the minimum 1 CPU / 1 GB RAM / 8 GB NVMe tariff permits only one database and one provider-managed user;
- additional PostgreSQL users are documented as unavailable on that minimum tariff;
- PostgreSQL user privileges include CREATE_ROLE;
- public, private and domain-based database connectivity are documented.

OWNER-selected beta configuration recorded on 2026-09-19:

- PostgreSQL 18;
- Moscow / MSK-1 / `ru-3`;
- 1 CPU;
- 2 GB RAM;
- 20 GB NVMe;
- base compute/database tariff: 790 RUB/month.

The 790 RUB decision covers the base DBaaS configuration only. Public IPv4 and backup-storage add-ons are separate provider charges and are not silently authorized by this source change.

The selected 2 GB configuration is intentionally above Timeweb's restricted 1 GB minimum. Timeweb documents that additional DB users and additional databases are unavailable only on the 1 CPU / 1 GB RAM / 8 GB NVMe minimum tier.

Timeweb documents scale-up as supported and scale-down as unsupported. Start small, measure beta load, and increase resources only when observed CPU/RAM/query/connection evidence requires it.

References:

- https://timeweb.cloud/docs/dbaas/dbaas-create
- https://timeweb.cloud/docs/dbaas/postgresql
- https://timeweb.cloud/docs/dbaas/postgresql/users-and-privileges
- https://timeweb.cloud/docs/dbaas/postgresql/roles
- https://timeweb.cloud/docs/dbaas/postgresql/connect-to-database
- https://timeweb.cloud/docs/zony-dostupnosti/servisy-i-zony-dostupnosti

## Source proof harness

The repository proof command is:

`python -m scripts.prove_v10_ru_postgres_timeweb_parity`

It consumes the privileged bootstrap DSN only from:

`OMNI_V10_RU_PG_BOOTSTRAP_DSN`

The value must never be placed in GitHub source, PR comments, CI output, screenshots or artifacts.

The proof also requires:

`OMNI_V10_RU_PG_SYNTHETIC_ACK=TIMEWEB_SYNTHETIC_ONLY`

and:

`OMNI_V10_RU_PG_PROVIDER_LOCATION=ru-3`

This value is only the expected provider location for the proof. It is not accepted provider-location evidence by itself. RU-PG-B still requires separate sanitized Timeweb control-plane evidence binding the real synthetic cluster to Moscow / MSK-1 / `ru-3`.

The DSN must use `sslmode=verify-full` and an externally provisioned `sslrootcert` path. The certificate file is operational input, not repository content.

The synthetic acknowledgement is a destructive-scope guard. It is not legal evidence and must never be used to justify real personal data.

## Proof sequence

The harness fails closed unless all of these pass:

1. target is not a Neon hostname;
2. the PostgreSQL connection requires `sslmode=verify-full` and an external CA root certificate;
3. the live PostgreSQL session is encrypted;
4. server major is exactly PostgreSQL 18;
5. bootstrap login is LOGIN, non-superuser and has CREATEROLE;
6. bootstrap identity is distinct from `omni_cio_hosted_api`;
7. current migrations apply and exact migration state matches source;
8. runtime role can be created or safely rotated;
9. runtime role remains LOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION and NOBYPASSRLS;
10. runtime role inherits from no broader role;
11. the accepted hosted runtime ACL SQL is reused unchanged;
12. broker tenant relations are ENABLE + FORCE ROW LEVEL SECURITY;
13. unscoped runtime reads return no tenant rows;
14. tenant A cannot read tenant B broker rows;
15. tenant A cannot insert a tenant B broker row.

Success is represented only by the sanitized marker:

`RU_PG_TIMEWEB_SYNTHETIC_PARITY=PASS`

The marker contains no DSN, username, password, host, account ID or private payload. It intentionally does not claim provider identity or location; those remain separate provider-verifiable evidence.

## Minimum-tier rule

Do not assume that SQL `CREATE ROLE` bypasses Timeweb's documented minimum-tier one-user limit.

The restricted 1 GB minimum tier remains rejected. The OWNER-selected 1 CPU / 2 GB RAM / 20 GB NVMe tier at the recorded 790 RUB/month base price is the RU-PG-B beta target. A distinct runtime login still has to succeed in real provider evidence; cost selection never weakens the identity boundary.

Security boundaries must not be collapsed to fit the cheapest tariff.

## Exit gate

RU-PG-B is not accepted merely because the source harness is GREEN.

Required real evidence:

- Timeweb cluster is PostgreSQL 18;
- provider location is Moscow / MSK-1 / ru-3;
- synthetic-only cluster;
- proof command returns the sanitized PASS marker;
- no secret/private values enter GitHub evidence;
- exact-head CI/Sonar/review is GREEN;
- merge + exact-new-main Regression Shield/Governance are GREEN.

Only then may RU-PG-C Cloudflare TLS/runtime + recovery parity begin.
