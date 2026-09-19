# V10 RU-PG-B — Timeweb Public IPv4 + Firewall + TLS Transport

Status: **SOURCE READY / PROVIDER MUTATION PENDING ACCEPTED MAIN**

Owning issue: #559

Accepted source base: `b45d110d92d6642b9f29a6866c4c2e06eab76dd4`.

## Purpose

This checkpoint implements the selected RU-PG-B transport
`PUBLIC_IPV4_OWNER_APPROVED` without weakening PostgreSQL TLS or exposing the
synthetic cluster to the whole Internet.

Source publication itself performs no provider mutation. Live mutation is manual,
protected-`main` only and uses GitHub Environment `timeweb-synthetic`.

## Authority and cost

The OWNER separately approved one Timeweb public IPv4 up to 200 RUB/month and
provided sanitized evidence of sufficient Timeweb balance.

This does not authorize IPv6, the DDoS add-on, backup storage, replicas, wider
firewall rules, `0.0.0.0/0`, production data, production DSN cutover, RU-PG-C,
public-user activation or broker-write authority.

## Verifier source boundary

The workflow discovers the self-hosted verifier's current public IPv4 from
Cloudflare's managed `/cdn-cgi/trace` endpoint. Two samples must agree and the
result must be a global-unicast IPv4. The value is converted to one `/32`, masked
for GitHub Actions, and passed only through the current job environment.

The exact address is not repository content and is not emitted in the sanitized
success marker. This /32 is RU-PG-B synthetic-proof authority only. It is not a
Cloudflare production-egress contract and is not inherited by RU-PG-C.

## Firewall-first invariant

Before public networking may be enabled, provider evidence must prove:

1. one firewall group named `omni-cio-v10-ru-pg-synthetic-verifier`;
2. policy `DROP`;
3. exactly one ingress rule;
4. protocol TCP;
5. port `5432`;
6. source equal to the current verifier `/32`;
7. the group linked only to the target Timeweb DBaaS resource;
8. the target DBaaS service belongs to exactly this one firewall group, so no second
   whitelist group can union additional ingress authority;
9. no wildcard rule and no unrelated resource link.

The Timeweb API uses `resource_type=dbaas` for this firewall association. The
provider CLI exposes the user-facing name `database` but maps it to `dbaas`.

The firewall rule, resource link and exclusive service-to-firewall membership are
verified before public access and again after public access is enabled.

If the target is unexpectedly already public when the workflow starts, it may
continue only when public IPv6 is off and the existing named group is DROP, contains
exactly one narrow global IPv4 /32 TCP/5432 rule, is linked only to the target DBaaS
resource, and is the target's only firewall group. Any pre-existing public IPv6 is
disabled immediately and treated as a blocking unsafe state. Any other unsafe public
state is also returned to public-network OFF before the run stops for reconciliation.

## Public IPv4 mutation

The workflow never silently consumes an unrelated free/unbound public IP.

If a new address is required, it permits exactly one
`POST /api/v1/floating-ips` with availability zone `msk-1` and
`is_ddos_guard=false`. An ambiguous create response is reconciled by GET and
set-difference; there is no blind second POST.

Only after the DROP firewall is exact does the workflow patch the database v2
network surface with:

- the selected floating IPv4;
- public IPv4 enabled;
- public IPv6 disabled;
- provider secure connection enabled.

## TLS verification

The Timeweb technical database domain must reach certificate status `issued`.
The verifier downloads the provider CA from
`https://st.timeweb.com/cloud-static/ca.crt` to a temporary permission-hardened
file. It then sends the PostgreSQL SSLRequest on TCP/5432 and enforces
`sslmode=verify-full` semantics by upgrading the socket using
`ssl.PROTOCOL_TLS_CLIENT`, a minimum protocol version of TLS 1.2,
`ssl.CERT_REQUIRED`, and hostname verification.

This is a credential-free network/TLS proof. Database credentials remain outside
this checkpoint.

If TLS, firewall re-verification or IPv4 binding verification fails after public
access may have been enabled, the workflow immediately attempts to disable public
networking again. If GET cannot prove the rollback, the run stops in a manual
reconciliation state and is never GREEN.

## Manual workflow

Workflow:

`.github/workflows/v10-timeweb-postgres-public-ipv4-tls.yml`

Exact confirmation:

`ENABLE_TIMEWEB_RU_PG_PUBLIC_IPV4_200_RUB_MONTH`

Before Timeweb secret access it:

1. bootstraps the exact protected-main SHA;
2. validates this source contract;
3. verifies the `timeweb-synthetic` main-only environment policy;
4. discovers and masks the current verifier /32;
5. validates the exact cost confirmation.

The Timeweb credential is injected only into the single provider-mutation step.

## Success marker

Only this sanitized marker is accepted:

`TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=READY`

No token, IPv4 value, firewall/rule/resource identifier, database identifier,
hostname, certificate, username, password or DSN is allowed in repository evidence.

## What remains

This checkpoint does not certify RU-PG-B. The subsequent synthetic database proof
must still establish separate bootstrap/runtime identities, PostgreSQL 18,
migrations plus retry idempotence, ALTER DEFAULT PRIVILEGES, least-privilege runtime
grants, RLS/FORCE RLS, unscoped default deny and cross-tenant negative tests.

Required parity marker:

`RU_PG_TIMEWEB_SYNTHETIC_PARITY=PASS`

Until that proof is accepted, Neon production authority remains unchanged and
RU-PG-C remains locked.

## Official references

- https://timeweb.cloud/docs/dbaas/dbaas-manage/public-ip-access
- https://timeweb.cloud/docs/dbaas/postgresql/connect-to-database
- https://timeweb.cloud/docs/firewall
- https://timeweb.cloud/docs/firewall/upravlenie-fajrvolom
- https://timeweb.cloud/docs/public-ip
- https://timeweb.cloud/docs/public-ip/create-public-ip
- https://developers.cloudflare.com/fundamentals/reference/cdn-cgi-endpoint/
- https://github.com/timeweb-cloud/twc
- https://github.com/timeweb-cloud/sdk-javascript
