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

The connection host must be the Timeweb technical **domain** on explicit port `5432`, not the public IPv4. P3 materializes the public Timeweb CA from `https://st.timeweb.com/cloud-static/ca.crt` before the production connection. The hosted runtime materializes that public CA once per process. Both reject redirects/non-certificate content and write the CA atomically to a permission-hardened local file. Only in-process connection copies use the absolute local CA path; the stored external DSN remains unchanged, so P3 can later require exact equality with the App Platform binding while Windows CI and the Linux runtime use their own local filesystem paths.

The CA is public trust material, not a credential. Never weaken this boundary by omitting `sslrootcert`, switching to `sslmode=require`/disabled verification, using the public IP as the verified host, or storing a machine-specific absolute CA path in the shared DSN.

The stored external DSN stays minimal and portable. After the provider hostname/address has been proven, the **in-process prepared conninfo** adds three mandatory authenticated-transport controls: `gssencmode=disable`, `sslcertmode=disable`, and `ssl_min_protocol_version=TLSv1.2`. PostgreSQL/libpq can otherwise prefer GSS encryption over SSL even when `sslmode` is set, and by default may send a client certificate from the standard per-user location if a server requests one. Omni-CIO does not delegate database transport or client identity to those ambient channels: authenticated traffic must remain on the same verify-full TLS boundary that the credential-free probe just proved. These controls are injected only into the process-local prepared DSN; OWNER does not add them to the GitHub/Timeweb secret value.

### Credential-free connection-readiness ladders

P3 verification and the Timeweb hosted runtime intentionally use different network routes while preserving the same authenticated TLS identity.

The P3 controller remains on the accepted verifier/public path:

`Timeweb technical-domain provenance -> public DNS resolution -> public TCP/5432 -> PostgreSQL SSLRequest -> TLS >= 1.2 + CA/hostname verification -> authenticated PostgreSQL connect`.

The hosted App Platform runtime uses the Timeweb private-network path selected at App creation:

`Timeweb technical-domain provenance -> explicit scoped RFC1918 private hostaddr -> private TCP/5432 -> PostgreSQL SSLRequest -> TLS >= 1.2 + CA/technical-hostname verification -> authenticated PostgreSQL connect`.

Current Timeweb Firewall documentation states that Firewall filtering does not operate inside private networks. Therefore the P3 verifier-only public firewall remains a control for the public verifier path only; it is neither a prerequisite for nor an authorization mechanism for App-to-PostgreSQL private traffic. Do not add a private-CIDR firewall rule merely to make the App route work, and do not weaken the public verifier firewall because the private route is separate.

The accepted provider technical-domain suffix set is `.tw1.ru`, `.tw1.su`, `.twc1.net`, and `.webtm.ru`. External DSNs remain strict allowlist inputs: only the contract-defined target, database, login, credential, and TLS fields are accepted. The stored DSN never contains `hostaddr`. For P3, the runtime preparation resolves and proves one public address. For App Platform, `OMNI_V10_POSTGRES_PRIVATE_HOSTADDR` is supplied separately and must be inside the exact RFC1918 `OMNI_V10_POSTGRES_PRIVATE_NETWORK_CIDR`; Timeweb-reserved service addresses are rejected. In both modes the prepared in-process conninfo keeps the original technical hostname as `host` for SNI/`verify-full` certificate identity and uses only the separately proved numeric address as `hostaddr`. Ambient libpq target/credential variables remain forbidden. Neither probe prints the technical hostname, public/private address, DSN, user, password, certificate body, or raw exception text.

Transport retries are bounded and only explicit transient DNS/TCP failures are replayed. Certificate, protocol, provider-domain, private-resolution and PostgreSQL authentication failures stop immediately. Database connection retries likewise require a classified transient failure; an unclassified client-side `OperationalError` is not replayed blindly.

The hosted runtime keeps the CA file stable for the process lifetime but **re-proves its private PostgreSQL route before every new pooled connection**, including replacement connections after a dropped/failed session. Each new connection repeats private TCP/SSLRequest/verify-full against the configured private service address while preserving the provider technical hostname for certificate identity. The private address and network are configuration bindings of the selected Timeweb VPC; they are never inferred from arbitrary DNS or accepted from the browser.

`connect_prepared_timeweb_postgres()` independently validates the prepared shape. By default it still requires a global/public `hostaddr` for the P3 verifier path. A private `hostaddr` is accepted only when the caller supplies an exact RFC1918 network scope and the address belongs to it. In both cases the original Timeweb hostname remains present for certificate identity, `sslmode=verify-full` remains intact, and `sslrootcert` is an absolute process-local path. A raw external DSN cannot bypass the readiness ladder by calling the prepared connector directly.

A successful P3 public credential-free boundary emits only:

`TIMEWEB_PG_TLS_TRANSPORT=READY dns=public tcp=5432 tls=verify-full`

A successful hosted-runtime private boundary emits only:

`TIMEWEB_PG_TLS_PRIVATE_TRANSPORT=READY tcp=5432 tls=verify-full route=private`

A RED emits a sanitized stage code. Treat these codes as operator routing, not as permission to weaken TLS or broaden ingress:

- `TIMEWEB_PG_TLS_DNS_RESOLUTION_FAILED`: provider technical DNS is not currently resolvable from the verifier/runtime;
- `TIMEWEB_PG_TLS_RESOLUTION_NOT_PUBLIC`: the external-production DSN does not resolve to an acceptable public target;
- `TIMEWEB_PG_TLS_TCP_TIMEOUT` / `...ROUTE_UNREACHABLE`: inspect Timeweb cluster/node health, the DB `Сеть` public-IPv4 `Разрешить доступ` state, and any attached firewall/source restriction; do not rotate credentials or downgrade TLS;
- `TIMEWEB_PG_TLS_TCP_REFUSED`: the endpoint is reachable but PostgreSQL/TCP is not accepting the connection yet;
- `TIMEWEB_PG_TLS_SSLREQUEST_REFUSED` / `...PROTOCOL_INVALID`: port 5432 did not present the expected PostgreSQL SSL negotiation;
- `TIMEWEB_PG_TLS_CERT_VERIFY_FAILED` / `...HANDSHAKE_FAILED`: stop and reconcile provider TLS/domain/CA state; never switch away from `verify-full`;
- `*_PASSWORD_REQUIRED`, `*_AUTHENTICATION_REJECTED`, `*_ROLE_NOT_FOUND`, `*_DATABASE_NOT_FOUND`, `*_HOST_POLICY_REJECTED`: deterministic database/authentication configuration failure; do not retry it as a network incident.

Timeweb documents that external PostgreSQL access requires public-IP access and that domain-based PostgreSQL connection uses protected TLS. A provider-side node incident or firewall drop can therefore coexist with valid source configuration and a valid CA while the live TCP connection still times out; source correctness alone is not transport readiness.

### Provider network-scope gate

Before any operation-specific database controller step receives production DSNs, the workflow validates all dispatch authority without secrets and validates/masks the exact current `verifier_cidr` as one global IPv4 `/32`. Ordinary `observe`, `prepare`, and `accept` then perform the existing **read-only** Timeweb provider-state proof. The bounded `bootstrap_prepare` recovery operation is the only exception: after explicit confirmation it may create the missing production firewall group/rule/resource link, and it must immediately pass the same read-only proof before any database authentication.

The provider proof binds the bootstrap DSN technical hostname to exactly one non-synthetic project database and requires: cluster `started`; PostgreSQL port `5432`; public IPv4 enabled and uniquely bound to that database; the public IPv4 in the same availability zone with DDoS add-on disabled; public IPv6 disabled; protected connection enabled with the exact hostname certificate issued; at least one attached firewall service group; every attached group must use policy `DROP` and link only the same production database resource; and the **effective union** of all attached-group rules must contain at least one rule while containing no semantic rule other than `ingress tcp/5432` from the supplied global `/32`. An individual same-type group may contain zero rules or a duplicate equivalent rule because Timeweb documents that a rule-less group is not applied and that rules from multiple same-type groups are combined. Duplicate group identities and duplicate provider rule identities are rejected. Firewall collection reads use bounded provider pagination and fail closed on total drift or truncation.

### Live P3 observe #5 — missing production firewall bootstrap

Accepted main `d440cdf859e34edb3b8727ef763347eab9a70803` reached the corrected provider-scope classifier and stopped before database authentication with `TIMEWEB_PG_PRODUCTION_FIREWALL_SERVICE_GROUP_MISSING`. This narrows the earlier #4 ambiguity: the old `...NOT_EXCLUSIVE` classifier represented both zero groups and multiple groups, so #4 never proved that multiple groups existed. The current provider observation proves the production database has **zero attached firewall groups** at the exact #5 observation.

Timeweb's current Firewall documentation states that a service with no effective firewall filtering remains reachable according to its underlying public-network configuration, and that allowlist groups deny traffic except for explicitly listed rules. Because the production database already has a public IPv4, a missing firewall group is a security prerequisite defect, not a condition to ignore in order to reach PostgreSQL faster.

The focused recovery path is `operation=bootstrap_prepare` with confirmation `BOOTSTRAP_AND_PREPARE_TIMEWEB_PRODUCTION_POSTGRES`. It is intentionally one-shot and narrow:

- it first proves the exact non-synthetic production target, public-IPv4 binding, TLS/certificate state, and verifier `/32`;
- if **any** firewall group is already attached, it performs no firewall mutation and lets the normal effective-union verifier decide whether the state is safe;
- only when zero groups are attached may it create/reuse the dedicated `omni-cio-v10-production-verifier` group with policy `DROP`;
- the dedicated group may contain only the exact ingress TCP/5432 rule from the current verifier `/32` and only the exact production DBaaS resource;
- existing wrong rules/resources or widened scope are terminal; the recovery path does not PATCH, DELETE, unlink, replace, or broaden them;
- ambiguous POST results are reconciled with bounded GET-only observations rather than blind mutation retry;
- after mutation, the ordinary two-pass `TIMEWEB_PG_PRODUCTION_NETWORK_SCOPE=READY` proof must pass;
- only then does the same workflow execute SQL-read-only `observe` followed by the existing bounded `prepare` migrations/ACL/RLS path.

This operation does not create App Platform, change DNS, enable Telegram/public users, change broker authority, or enable Real Trading.

A live P3 observe on accepted main `f57e088d4188da4ceec387c82f8b3b847fc6e0bb` exposed a verifier/provider semantic mismatch: the repository rejected the production database solely because more than one same-type Timeweb firewall group was attached, even though Timeweb explicitly allows that state and unions the rules. The corrected gate therefore evaluates the complete effective group union instead of requiring an invented single-group cardinality or an invented per-group rule cardinality. This does not weaken the network boundary: the union must still contain the exact verifier rule and nothing else; any attached group with a non-DROP policy, wrong/extra semantic rule, different CIDR, extra resource, malformed identity, duplicate provider identity, or snapshot drift remains terminal before database authentication.

The proof is intentionally not a single composite read. It performs **two consecutive read-only provider snapshots** and builds an in-memory stability witness from the production database identity, availability zone, floating-IP identity/address, firewall group, firewall rule, linked resource, and verifier CIDR. Every individual pass must be valid, and both witnesses must be identical. A mismatch stops with `TIMEWEB_PG_PRODUCTION_NETWORK_SNAPSHOT_DRIFT` before database authentication. Witness values are never printed. The database detail must also preserve the exact project identity selected through the authenticated project resource list. For the bound public IPv4, each pass reconciles the account-level floating-IP list row with a second exact floating-IP detail GET; any network-identity disagreement stops with `TIMEWEB_PG_PRODUCTION_FLOATING_IP_LIST_DETAIL_DRIFT`. Malformed provider domain, floating-IP, firewall-rule, or firewall-resource identities fail closed instead of being silently skipped. This prevents a valid-looking READY result assembled from stale list data, cross-project drift, or mutually inconsistent control-plane states while an external actor is changing the provider configuration.

A successful provider-scope proof emits only:

`TIMEWEB_PG_PRODUCTION_NETWORK_SCOPE=READY public_ipv4=bound ipv6=off tls=enabled firewall=drop ingress=tcp/5432 source=/32`

It never prints the hostname, verifier CIDR, database ID, firewall ID or public IP. The floating-IP list/detail comparison and database project identity are provider-side control-plane evidence only; their raw values also remain private. A provider-scope STOP occurs **before database authentication**. Only after this read-only provider proof may the credential-free DNS/TCP/SSLRequest/verify-full ladder run and then present PostgreSQL credentials.

The production cutover workflow shares the `v10-timeweb-postgres-public-ipv4-tls` concurrency group with the existing Timeweb network/allocation workflows so repository-controlled public-IP/firewall mutation cannot race the preflight. The double-read stability witness additionally detects provider-state drift that occurs during the preflight itself. Neither mechanism can serialize an unrelated external writer after the second snapshot, so manual Timeweb dashboard changes and unrelated API writers must remain frozen during P3 execution. The subsequent credential-free transport probe is still mandatory because a stable, correct provider configuration does not prove that the current verifier route is reachable.

## GitHub production-environment prerequisite

Before the first P3 dispatch, the repository GitHub Environment `timeweb-production` must already exist. Its deployment policy must be **Selected branches and tags** with exactly one rule: **Branch `main`**. The workflow only has read authority over this policy and must never create or relax the environment itself.

The same environment must hold `OMNI_V10_TIMEWEB_PROD_BOOTSTRAP_DSN` and `OMNI_V10_TIMEWEB_PROD_RUNTIME_DSN` as environment secrets. Do not paste either value into source, issues, chat, workflow inputs, screenshots, or logs. The current verifier source is supplied separately as the manual `verifier_cidr` workflow input, must be one global IPv4 `/32`, and is masked before provider-secret access.

A first-run `TIMEWEB_GITHUB_ENVIRONMENT_GATE_NOT_FOUND` means the environment has not been established. `...AUTHENTICATION_FAILED` or `...PERMISSION_DENIED` means stop and repair GitHub access; do not retry the production operation blindly.

## Ordered execution

1. PR #584 P2 source and exact-head verification is GREEN and the implementation is accepted on protected `main`.
2. Establish the dedicated production PostgreSQL 18 database and the pre-existing `omni_cio_hosted_api` login without exposing credentials.
3. Establish the `timeweb-production` GitHub Environment, exact-main branch policy, and the two production DSN secrets described above.
4. Invoke the P3 workflow with the exact accepted main SHA and the current global verifier `verifier_cidr` `/32`. When the production firewall already passes the provider-scope gate, `operation=observe` remains the read-only path. When the exact stop is `TIMEWEB_PG_PRODUCTION_FIREWALL_SERVICE_GROUP_MISSING`, use `operation=bootstrap_prepare` with confirmation `BOOTSTRAP_AND_PREPARE_TIMEWEB_PRODUCTION_POSTGRES`. That bounded operation converges only the missing DROP + TCP/5432 + verifier-/32 + exact-production-resource firewall boundary, re-runs the full provider-scope proof, runs SQL-read-only observe, and then proceeds directly into prepare.
5. If `observe` was used separately and succeeded, run `operation=prepare` with confirmation `PREPARE_TIMEWEB_PRODUCTION_POSTGRES`. Do not run a second prepare merely because `bootstrap_prepare` already completed it.
6. The controller verifies PostgreSQL 18/TLS, applies canonical migrations twice to prove retry idempotence, applies the canonical runtime ACL bootstrap, verifies the least-privilege runtime role, RLS/FORCE-RLS, tenant security constraints, and requires clean product identity/session/broker tables. A successful prepare emits the non-secret `postgres_binding_sha256` required for App bootstrap.
7. Create a Timeweb physical backup recovery point. Physical backup is mandatory and additive to the repository logical recovery contract.
8. Perform a separate restore rehearsal. If Timeweb exposes no documented safe API for the required recovery operation, use the bounded Timeweb panel action. Do not invent an undocumented endpoint.
9. Record recovery acceptance through the manual workflow input `recovery_attestation=TIMEWEB_PHYSICAL_BACKUP_AND_SEPARATE_RESTORE_REHEARSAL_ACCEPTED` and provide `recovery_evidence_sha256` as the SHA-256 of sanitized external recovery evidence. The attestation and digest are not credentials and must not be stored as Actions secrets. Never record provider backup IDs, raw backup payloads, credentials, or private account identifiers in source or CI output.
10. Create/configure the Timeweb App Platform candidate only in the already selected shared private network. Keep the verified production runtime DSN unchanged as TLS identity/credential authority and bind the private PostgreSQL address plus exact private-network CIDR through `OMNI_V10_POSTGRES_PRIVATE_HOSTADDR` and `OMNI_V10_POSTGRES_PRIVATE_NETWORK_CIDR`. Also set `OMNI_V10_POSTGRES_BINDING_SHA256` to the non-secret digest emitted by this exact accepted P3 `prepare` run. The digest excludes the password and binds the expected host/port/database/runtime user/TLS contract. P3 source intentionally does not patch App Platform settings because no undocumented settings endpoint is allowed.
11. Deploy the exact accepted-main P2 candidate on its Timeweb technical hostname. Require HTTPS `/livez` exact-SHA proof **and** HTTPS `/healthz` with `status=ok`, `database=READY`, and `synthetic_preview=false`. A process-only liveness success cannot prove App-to-PostgreSQL reachability.
12. Run `operation=accept`. The controller re-verifies the production database, read-only verifies that Timeweb App Platform holds the same runtime DSN, the exact accepted main SHA, and both public-user activation flags remain false, then independently repeats the P2 candidate observation against the Timeweb technical domain. Acceptance therefore requires the exact-SHA HTTPS `/livez` proof and HTTPS `/healthz status=ok database=READY synthetic_preview=false` at P3 acceptance time; an earlier P2 result is not trusted as a substitute for current route evidence.
13. Only after P3 acceptance may P4 canonical `omnicio.ru` DNS/TLS cutover begin.

## Failure and recovery

### Current live stop — no production firewall attached

Run #5 on accepted main `d440cdf859e34edb3b8727ef763347eab9a70803` stopped with `TIMEWEB_PG_PRODUCTION_FIREWALL_SERVICE_GROUP_MISSING` before database authentication. Do not rerun the same `observe` expecting a different outcome and do not disable the provider-scope guard. The repair is to land the reviewed `bootstrap_prepare` chain, then execute that exact accepted-main operation once with the current verifier `/32`. If it finds any attached group at execution time, it refuses to bootstrap around it and falls back to the normal fail-closed effective-union proof.

### Live P3 observe RED #2 — bootstrap transport collapse

Manual run `36276384123` on exact accepted main `2a7c7104e4e0d5bd2e6eee2f9b87fd71ed7b822d` passed exact-main/source/environment policy, then exhausted seven 15-second bootstrap connection attempts and stopped with the old generic `TIMEWEB_PG_PRODUCTION_BOOTSTRAP_CONNECTION_FAILED` marker. No `prepare` or `accept` step ran, so no production SQL mutation occurred.

That marker proves a live connection failure but cannot distinguish DNS, public-IP/firewall/routing, SSLRequest/TLS, provider-node readiness, or authentication because the old no-SQLSTATE path treated every client-side `OperationalError` as retryable. Do not rerun that source blindly. The connectivity-diagnostic repair replaces this collapsed boundary with the credential-free readiness ladder and classified authenticated-connect failures above. The later provider-scope repair additionally proves the Timeweb public-IP/firewall/TLS control-plane state before any database authentication. If that scope gate is READY but the credential-free TCP stage still times out, the remaining failure boundary is route/source/provider reachability rather than an unobserved firewall-policy assumption.

Any SHA mismatch, TLS downgrade, migration drift, widened runtime role, RLS/FORCE-RLS drift, non-empty clean-target tables, missing recovery attestation or evidence digest, App Platform DSN mismatch, or public-user flag enablement is `DEPLOYMENT_BLOCKED`.

Do not repair a failed P3 by dropping schemas, truncating data, weakening RLS, granting broad predefined roles, bypassing certificate verification, changing CI assertions, or enabling public users.

The last-known-good application release remains the application rollback target. Database recovery uses the accepted Timeweb physical backup plus the provider-neutral logical recovery contract. P3 acceptance does not authorize destructive removal of older recovery points.

Provider references for this boundary:
- https://timeweb.cloud/docs/dbaas/postgresql — managed PostgreSQL uses Patroni/Etcd leader-replica failover;
- https://timeweb.cloud/docs/dbaas/postgresql/connect-to-database — domain connections use protected TLS;
- https://timeweb.cloud/docs/firewall/upravlenie-fajrvolom — Timeweb Firewall does not filter traffic inside private networks;
- https://timeweb.cloud/docs/dbaas/dbaas-manage/public-ip-access — external access requires enabled public IP access.
- https://www.postgresql.org/docs/18/libpq-connect.html — `hostaddr`, GSS/SSL connection parameters and libpq connection semantics.
- https://www.postgresql.org/docs/18/libpq-ssl.html — verify-full server identity and default client-certificate file behavior.
