# V10 Timeweb PostgreSQL 18 Production Cutover Runbook

Scope: P3 of `TIMEWEB-PLATFORM-CONSOLIDATION-INTEGRATED` in PR #584.

This runbook never authorizes public users, Telegram activation, DNS changes, broker write, or Real Trading. Secret DSNs, passwords, provider tokens, backup identifiers, and private account identifiers must not be written to GitHub, chat, CI logs, screenshots, or artifacts.

## Production target rule

The production PostgreSQL target must be a Timeweb Cloud Managed PostgreSQL 18 database that is distinct from the historical synthetic parity target. Do not promote a synthetic database containing test Tenant/User/session fixtures into production.

The runtime login is `omni_cio_hosted_api`. It must already exist through the accepted Timeweb provider-user boundary. The P3 controller does not create the login and does not rotate its password. It only applies canonical migrations and provider-neutral runtime ACL/RLS bootstrap to the verified production database.

Both bootstrap and runtime DSNs must use `sslmode=verify-full` and an explicit `sslrootcert`. Retired-provider database hosts are rejected.

### Portable CA / DSN rule

P3 accepts PostgreSQL/libpq connection strings only. Do not copy the Timeweb panel's `pgsql:host=...` DSN form into GitHub: that is the PHP/PDO presentation and is not valid psycopg/libpq conninfo.

The external bootstrap/runtime DSNs and the later Timeweb App Platform `OMNI_V10_POSTGRES_DSN` must use the same portable root-certificate value:

`sslrootcert=.omni-cio/timeweb-postgres-root.crt`

The connection host must be the Timeweb technical **domain** on explicit port `5432`, not the public IPv4. Immediately before the first PostgreSQL connection, both the P3 verifier and the hosted runtime fetch the public Timeweb CA only from `https://st.timeweb.com/cloud-static/ca.crt`, reject redirects/non-certificate content, write it atomically to a permission-hardened local file, and rewrite only the in-process connection copy to the absolute local CA path. The stored external DSN remains unchanged, so P3 can later require exact equality with the App Platform binding while Windows CI and the Linux runtime use their own local filesystem paths.

The CA is public trust material, not a credential. Never weaken this boundary by omitting `sslrootcert`, switching to `sslmode=require`/disabled verification, using the public IP as the verified host, or storing a machine-specific absolute CA path in the shared DSN.

### Credential-free connection-readiness ladder

Before any database password is presented, P3 and the Timeweb hosted runtime prove the live boundary in ordered stages:

`Timeweb technical-domain provenance -> public DNS resolution -> TCP/5432 -> PostgreSQL SSLRequest -> TLS >= 1.2 + CA/hostname verification -> authenticated PostgreSQL connect`.

The accepted provider technical-domain suffix set is `.tw1.ru`, `.tw1.su`, `.twc1.net`, and `.webtm.ru`. Arbitrary domains and any private/reserved DNS resolution are rejected before database authentication. External DSNs are also strict allowlist inputs: only `host`, `port`, `dbname`, `user`, explicit `password`, `sslmode`, and `sslrootcert` are accepted. `hostaddr`, libpq service/passfile indirection, client-certificate overrides, and other ambient target/credential inputs are therefore rejected instead of bypassing the verified host/CA path. The probe never prints the technical hostname, resolved IP, DSN, user, password, certificate body, or raw exception text.

Transport retries are bounded and only explicit transient DNS/TCP failures are replayed. Certificate, protocol, provider-domain, private-resolution and PostgreSQL authentication failures stop immediately. Database connection retries likewise require a classified transient failure; an unclassified client-side `OperationalError` is not replayed blindly.

A successful credential-free boundary emits only:

`TIMEWEB_PG_TLS_TRANSPORT=READY dns=public tcp=5432 tls=verify-full`

A RED emits a sanitized stage code. Treat these codes as operator routing, not as permission to weaken TLS or broaden ingress:

- `TIMEWEB_PG_TLS_DNS_RESOLUTION_FAILED`: provider technical DNS is not currently resolvable from the verifier/runtime;
- `TIMEWEB_PG_TLS_RESOLUTION_NOT_PUBLIC`: the external-production DSN does not resolve to an acceptable public target;
- `TIMEWEB_PG_TLS_TCP_TIMEOUT` / `...ROUTE_UNREACHABLE`: inspect Timeweb cluster/node health, the DB `Сеть` public-IPv4 `Разрешить доступ` state, and any attached firewall/source restriction; do not rotate credentials or downgrade TLS;
- `TIMEWEB_PG_TLS_TCP_REFUSED`: the endpoint is reachable but PostgreSQL/TCP is not accepting the connection yet;
- `TIMEWEB_PG_TLS_SSLREQUEST_REFUSED` / `...PROTOCOL_INVALID`: port 5432 did not present the expected PostgreSQL SSL negotiation;
- `TIMEWEB_PG_TLS_CERT_VERIFY_FAILED` / `...HANDSHAKE_FAILED`: stop and reconcile provider TLS/domain/CA state; never switch away from `verify-full`;
- `*_PASSWORD_REQUIRED`, `*_AUTHENTICATION_REJECTED`, `*_ROLE_NOT_FOUND`, `*_DATABASE_NOT_FOUND`, `*_HOST_POLICY_REJECTED`: deterministic database/authentication configuration failure; do not retry it as a network incident.

Timeweb documents that external PostgreSQL access requires public-IP access and that domain-based PostgreSQL connection uses protected TLS. A provider-side node incident or firewall drop can therefore coexist with valid source configuration and a valid CA while the live TCP connection still times out; source correctness alone is not transport readiness.

## GitHub production-environment prerequisite

Before the first P3 dispatch, the repository GitHub Environment `timeweb-production` must already exist. Its deployment policy must be **Selected branches and tags** with exactly one rule: **Branch `main`**. The workflow only has read authority over this policy and must never create or relax the environment itself.

The same environment must hold `OMNI_V10_TIMEWEB_PROD_BOOTSTRAP_DSN` and `OMNI_V10_TIMEWEB_PROD_RUNTIME_DSN` as environment secrets. Do not paste either value into source, issues, chat, workflow inputs, screenshots, or logs.

A first-run `TIMEWEB_GITHUB_ENVIRONMENT_GATE_NOT_FOUND` means the environment has not been established. `...AUTHENTICATION_FAILED` or `...PERMISSION_DENIED` means stop and repair GitHub access; do not retry the production operation blindly.

## Ordered execution

1. PR #584 P2 source and exact-head verification is GREEN and the implementation is accepted on protected `main`.
2. Establish the dedicated production PostgreSQL 18 database and the pre-existing `omni_cio_hosted_api` login without exposing credentials.
3. Establish the `timeweb-production` GitHub Environment, exact-main branch policy, and the two production DSN secrets described above.
4. Invoke the P3 workflow with the exact accepted main SHA and `operation=observe`. The observe phase is SQL read-only: it verifies target identity, PostgreSQL 18, TLS, bootstrap/runtime role authority and absence of product-data residue without applying migrations, ACLs, RLS, or cross-tenant write probes.
5. Run `operation=prepare` with confirmation `PREPARE_TIMEWEB_PRODUCTION_POSTGRES`.
6. The controller verifies PostgreSQL 18/TLS, applies canonical migrations twice to prove retry idempotence, applies the canonical runtime ACL bootstrap, verifies the least-privilege runtime role, RLS/FORCE-RLS, tenant security constraints, and requires clean product identity/session/broker tables.
7. Create a Timeweb physical backup recovery point. Physical backup is mandatory and additive to the repository logical recovery contract.
8. Perform a separate restore rehearsal. If Timeweb exposes no documented safe API for the required recovery operation, use the bounded Timeweb panel action. Do not invent an undocumented endpoint.
9. Record recovery acceptance through the manual workflow input `recovery_attestation=TIMEWEB_PHYSICAL_BACKUP_AND_SEPARATE_RESTORE_REHEARSAL_ACCEPTED` and provide `recovery_evidence_sha256` as the SHA-256 of sanitized external recovery evidence. The attestation and digest are not credentials and must not be stored as Actions secrets. Never record provider backup IDs, raw backup payloads, credentials, or private account identifiers in source or CI output.
10. Promote the verified production runtime DSN to the existing Timeweb App Platform application through documented provider controls. P3 source intentionally does not patch App Platform settings because no undocumented settings endpoint is allowed.
11. Run `operation=accept`. The controller re-verifies the production database and then read-only verifies that Timeweb App Platform holds the same runtime DSN, the exact accepted main SHA, and both public-user activation flags remain false.
12. Only after P3 acceptance may P4 canonical `omnicio.ru` DNS/TLS cutover begin.

## Failure and recovery

### Live P3 observe RED #2 — bootstrap transport collapse

Manual run `36276384123` on exact accepted main `2a7c7104e4e0d5bd2e6eee2f9b87fd71ed7b822d` passed exact-main/source/environment policy, then exhausted seven 15-second bootstrap connection attempts and stopped with the old generic `TIMEWEB_PG_PRODUCTION_BOOTSTRAP_CONNECTION_FAILED` marker. No `prepare` or `accept` step ran, so no production SQL mutation occurred.

That marker proves a live connection failure but cannot distinguish DNS, public-IP/firewall/routing, SSLRequest/TLS, provider-node readiness, or authentication because the old no-SQLSTATE path treated every client-side `OperationalError` as retryable. Do not rerun that source blindly. The connectivity-diagnostic repair replaces this collapsed boundary with the credential-free readiness ladder and classified authenticated-connect failures above.

Any SHA mismatch, TLS downgrade, migration drift, widened runtime role, RLS/FORCE-RLS drift, non-empty clean-target tables, missing recovery attestation or evidence digest, App Platform DSN mismatch, or public-user flag enablement is `DEPLOYMENT_BLOCKED`.

Do not repair a failed P3 by dropping schemas, truncating data, weakening RLS, granting broad predefined roles, bypassing certificate verification, changing CI assertions, or enabling public users.

The last-known-good application release remains the application rollback target. Database recovery uses the accepted Timeweb physical backup plus the provider-neutral logical recovery contract. P3 acceptance does not authorize destructive removal of older recovery points.
