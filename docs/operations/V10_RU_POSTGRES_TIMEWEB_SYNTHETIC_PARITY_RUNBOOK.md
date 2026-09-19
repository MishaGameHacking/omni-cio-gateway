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

The synthetic acknowledgement is a destructive-scope guard. It is not legal evidence and must never be used to justify real personal data.

## Proof sequence

The harness fails closed unless all of these pass:

1. target is not a Neon hostname;
2. the PostgreSQL session is encrypted;
3. server major is exactly PostgreSQL 18;
4. bootstrap login is LOGIN, non-superuser and has CREATEROLE;
5. bootstrap identity is distinct from `omni_cio_hosted_api`;
6. current migrations apply and exact migration state matches source;
7. runtime role can be created or safely rotated;
8. runtime role remains LOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION and NOBYPASSRLS;
9. runtime role inherits from no broader role;
10. the accepted hosted runtime ACL SQL is reused unchanged;
11. broker tenant relations are ENABLE + FORCE ROW LEVEL SECURITY;
12. unscoped runtime reads return no tenant rows;
13. tenant A cannot read tenant B broker rows;
14. tenant A cannot insert a tenant B broker row.

Success is represented only by the sanitized marker:

`RU_PG_TIMEWEB_SYNTHETIC_PARITY=PASS`

The marker contains no DSN, username, password, host, account ID or private payload.

## Minimum-tier rule

Do not assume that SQL `CREATE ROLE` bypasses Timeweb's documented minimum-tier one-user limit.

The minimum tier stays rejected until the real provider proof actually succeeds with a distinct runtime login. If the provider blocks role creation, RU-PG-B remains RED and the next cheapest configuration that supports the required identity split needs fresh OWNER cost approval.

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
