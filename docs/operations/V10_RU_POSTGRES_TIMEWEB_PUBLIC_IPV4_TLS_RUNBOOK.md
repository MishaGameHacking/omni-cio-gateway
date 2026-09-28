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

This does not authorize IPv6, the DDoS add-on, backup storage, additional paid
replication, wider firewall rules, `0.0.0.0/0`, production data, production DSN cutover, RU-PG-C,
public-user activation or broker-write authority.

## Verifier source boundary

The manual workflow requires the exact current self-hosted verifier global IPv4
as the explicit `verifier_cidr` dispatch input. The input must already be one
global-unicast IPv4 `/32`; repository code performs no external IP-echo/discovery
request. The validator canonicalizes the value, masks both the address and CIDR,
and passes it only through the current job environment.

The exact address is not repository content and is not emitted in the sanitized
success marker. This /32 is RU-PG-B synthetic-proof authority only and is not
inherited by RU-PG-C. A missing, malformed, non-global or non-/32 value fails
closed before Timeweb provider authority is constructed.

The validator does not discover NAT egress; successful live TCP/TLS through the exact firewall `/32` is the only repository-owned data-plane evidence that this source authority actually admits the verifier path.

## Provider disk unit contract

The pre-mutation cluster-shape proof reuses the same Timeweb unit contract as the
synthetic-create recovery path: DB preset `disk` is MB, but
`DatabaseCluster.disk.size` returned by cluster GET is KB. The accepted target
is therefore `20480 MB` at preset selection and exactly `20971520 KB` at
cluster verification. Fractional, undersized, oversized or malformed values fail
closed before firewall or public-network mutation.

## Canonical replica topology precondition

Accepted automatic Read-Only Proof run `35507498165` on exact main `3a96dfe88e99aac754d8949725122295dd957429` observed `replica_list_count=1` for the approved base cluster. Before any firewall or public-network mutation, this workflow reuses the same canonical count-only topology verifier as Synthetic Create: provider replica-list baseline count is exactly `1`, every member must belong to the exact target cluster, duplicate member IDs are forbidden, and any count drift fails closed. This count-only baseline preserves the rule that additional paid replication remains unauthorized; a non-empty raw provider list is not by itself treated as proof of a paid add-on.

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

The current transport no longer has authority to create, stamp or delete a
floating IPv4. The durable allocation receipt is a mandatory predecessor and the
transport must recover exactly that already-managed address from two consistent
GET observations. If the allocated address is missing or the two observations
drift, the run stops with `TIMEWEB_ALLOCATED_IPV4_MISSING` or
`TIMEWEB_ALLOCATED_IPV4_DRIFT`; it never converts that drift into a new purchase.

Only after the DROP firewall is exact does the workflow perform the provider
transitions in the documented order. The first database v2 PATCH contains only:

- the selected floating IPv4;
- public IPv4 enabled;
- public IPv6 disabled.

The workflow then GET-reconciles the database and floating-IP binding, re-verifies
the narrow firewall/resource scope, and only after public IPv4 is proved does a
second database v2 PATCH request provider secure connection. TLS enablement is
therefore never combined with first-time public IPv4 attachment.

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

## Durable allocation prerequisite

Live transport run #4 on exact main `0b2eabed43ba7a60696c1f24ccb33833cba9091b`
proved that source/environment/cost gates can all pass while the provider still
contains one `unproven_unbound` IPv4. It stopped before firewall/network/TLS
mutation with `TIMEWEB_IPV4_ORPHAN_PROVENANCE_REQUIRED`.

The transport workflow now requires the safe non-authorizing
`allocation_plan_id` produced by the existing-IPv4 allocation workflow. Inside
the sole provider-secret step, the code opens the protected Windows journal,
requires a durable `ALLOCATED` allocation receipt, then performs two equal GET-only canonical
provider snapshots and binds the receipt to the same account/project/cluster/IP
identity plus the accepted custody marker before `TimewebMutationApi` exists.

The receipt permits only the same managed IP while it is either unbound or bound
to the exact target database. Public-network and IPv6 booleans are intentionally
not receipt identity: the existing transport recovery code owns those states and
can safely close an unexpected exposure. Any foreign binding, changed address,
changed target, changed marker or inconsistent GET pair is a hard stop. The
existing custody preflight rechecks provider state again immediately before
firewall/network/TLS mutation.

A `PLANNED`, `ATTEMPTED`, missing or corrupt receipt is also a hard stop. An
ambiguous allocation attempt must use GET-only `RECONCILE`; transport is never
allocation recovery.

## Manual workflow

Workflow:

`.github/workflows/v10-timeweb-postgres-public-ipv4-tls.yml`

Exact confirmation:

`ENABLE_TIMEWEB_RU_PG_PUBLIC_IPV4_200_RUB_MONTH`

Required verifier and safe allocation inputs:

`verifier_cidr=<exact current global IPv4/32>`

`allocation_plan_id=<safe plan handle from verified allocation>`

Before provider mutation authority is constructed it:

1. bootstraps the exact protected-main SHA;
2. validates this source contract;
3. verifies the `timeweb-synthetic` main-only environment policy;
4. validates and masks the explicit verifier /32 without any external discovery service;
5. validates the exact cost confirmation;
6. proves the durable ALLOCATED receipt against two current provider GET snapshots.

The Timeweb credential is injected only into the single provider step; mutation
authority is constructed only after the receipt/resource proof succeeds.


## Live RED #1 — mutation rejection recovery

Manual workflow run `35515788859` on exact protected main
`51b4e37492987bf034dbf44247b03e23a0dd5aff` reached the provider mutation step
after all pre-mutation gates passed:

- source contract: PASS;
- verifier CIDR input validation: `RU_PG_VERIFIER_CIDR=READY source=workflow_input mask=/32`;
- GitHub Environment gate: `TIMEWEB_GITHUB_ENVIRONMENT_GATE=READY`;
- exact cost confirmation: PASS.

The provider step then stopped with only:

`TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=STOPPED code=TIMEWEB_MUTATION_REJECTED`.

That original marker does **not** prove which mutation or HTTP rejection status failed.
The old adapter intentionally discarded the provider response body, but it also collapsed
every non-authentication deterministic HTTP rejection into the same stop code. Therefore
the exact external rejection cause cannot be reconstructed from run #1 and must not be
invented.

The repair keeps response bodies, response IDs, resource IDs, IP addresses, hostnames and
secrets out of logs while making future evidence actionable:

- each provider mutation has a stable operation-specific stop code;
- a numeric HTTP status may be emitted because it contains no credential/private payload;
- provider response bodies remain unread/unlogged;
- bodyless mutating POST requests use `Content-Type: application/json`, matching the
  current generated Timeweb SDK wire contract for firewall resource linking;
- conflict/locked states `409/423` enter GET-only reconciliation where the caller
  already has an exact state verifier; they never trigger a blind second mutation;
- expected success statuses are tightened to the current provider SDK contract
  (`201` for firewall/floating-IP creates and resource linking, `200` for PATCH,
  `204` for cleanup DELETE).

This is a recovery/diagnostic hardening checkpoint, not evidence that public IPv4 or TLS
is already ready. A fresh protected-main live run is still required after this repair is
accepted. Any new RED must be diagnosed from its operation-specific sanitized marker
before another provider mutation attempt.

The create/stamp/delete mechanics described in the historical RED/recovery sections
below explain how the original allocation defect class was discovered and repaired.
They are no longer current Public IPv4/TLS transport authority after the accepted
existing-IPv4 allocation receipt. Current transport is existing-only as defined
above and in the machine contract.

## Live RED #2 - IPv4 custody and restart recovery

Run `35519666168`, after PR #573, stopped before another IPv4 create with
`TIMEWEB_UNMANAGED_FREE_IPV4_PRESENT`. That proves that the old parser saw an
unbound-shaped row, not its origin, zone, exact identity or ownership. A missing
binding field was also previously treated as empty. Do not infer that run #1
created this address or that it is safe to adopt it.

The defect class is `TIMEWEB_PUBLIC_IPV4_RECOVERY_PROVENANCE_GAP`. The old state
machine remembered `created_this_run` only in process memory, had no durable
management association, and stopped on every unbound row. Its source guard checked
happy-path markers, while mutation mocks did not exercise crash/restart custody,
ambiguous create attribution or cleanup confirmation. The guard against arbitrary
IP adoption was correct and is retained, not suppressed.

The shared custody adapter now normalizes complete inventories, rejects duplicate
IDs/addresses, missing/malformed binding fields and incomplete `meta.total`, and
emits only aggregate counts. The inventory preflight occurs before firewall
convergence; unsafe pre-existing public exposure still takes the existing emergency
close path first. No caller may interpret `None`, an invalid response or a failed
GET as an empty account.

Selection is intentionally narrow:

- an exact target-bound IPv4 may be reused after two agreeing GET observations;
- one unbound IPv4 can be recovered only with an exact management association for
  this repository, stage, target cluster, address identity and address value;
- an unmarked or unrelated unbound IPv4 still stops with
  `TIMEWEB_IPV4_ORPHAN_PROVENANCE_REQUIRED`;
- ambiguous/multiple candidates, wrong zone, DDoS-enabled resources, reassignment
  or conflicting target associations stop before purchase/bind authority;
- a new address is eligible only when no conflicting resource exists. There is
  exactly one POST. A successful create receipt must match the unique fresh GET
  delta before any comment is stamped.

A unique GET delta alone is not a create receipt: an independent account operator
could have created it. An ambiguous create therefore reconciles visibility by GET
but does not stamp, adopt, delete or blindly retry a resource without a receipt.
`TIMEWEB_FLOATING_IP_CREATE_RECEIPT_UNPROVEN` is a reconciliation boundary.

The current Timeweb SDK separates `CreateFloatingIp` from `UpdateFloatingIp`:
create accepts zone/DDoS fields; `comment` is set by a separate PATCH returning
HTTP 200. The sole added mutation is
`PATCH /api/v1/floating-ips/{floating_ip_id}` with a comment-only body and operation
`FLOATING_IP_CUSTODY_STAMP`. It cannot change PTR, zone, DDoS or a binding. The
comment prefix is `omni-cio:ru-pg-b:ipv4:v1:` with a SHA-256 target/resource digest.
Neither that digest nor private identifiers enter log output.

This comment is a management association inside the already trusted provider
account. It is not a signature, immutable creation history or protection against
an administrator with provider-write authority. It must never be retroactively
written to today's unmarked address merely because it has compatible settings.
The workflow concurrency lock does not serialize unrelated dashboard/API writers;
those writers must remain frozen during the transition. Repeated GETs detect
observed drift but do not provide provider-side atomic compare-and-set semantics.

Create and stamp are NOT atomic. A crash before stamping can leave an unmarked
resource requiring separate external reconciliation. A confirmed managed orphan
can be recovered without another purchase; its `created_this_run` remains false,
so same-run cleanup cannot delete it. A stamp failure may clean only the exact
verified resource created during that attempt, while still unbound and without a
foreign comment. DELETE is not retried; GET must prove absence. Failed rollback or
unproven cleanup stays STOPPED and requires reconciliation.

### Read-only evidence and current legacy blocker

The existing protected-main Read-Only Proof also executes
`python -m scripts.probe_v10_timeweb_ipv4_custody` using the existing single
step-scoped Timeweb credential. Its source gate runs before provider access.
The observer uses GET only and does not import the mutation adapter. It emits:

`TIMEWEB_RU_PG_IPV4_INVENTORY=OBSERVED`

and a separate static `TIMEWEB_RU_PG_IPV4_RECOVERY=BLOCKED` or
`TIMEWEB_RU_PG_IPV4_RECOVERY=ELIGIBLE` disposition. A successful read-only run can
correctly report BLOCKED; it proves observation, not transport or SQL readiness.
Malformed/unavailable evidence makes the observer itself fail, rather than making
an empty-inventory or activation claim.

The exact synthetic database target may legitimately be absent at this earlier read-only
checkpoint. The control-plane probe already treats that state as
`existing_target=false` / `cluster_name_available=true`; the IPv4 observer must therefore
treat the same provider state consistently. It still reads and structurally validates the
complete account-level `/api/v1/floating-ips` inventory, emits only aggregate counts with
`target=absent`, and emits
`TIMEWEB_RU_PG_IPV4_RECOVERY=BLOCKED code=TIMEWEB_IPV4_TARGET_ABSENT` while returning a
successful observation result. It must not fabricate a cluster id, management marker,
target binding, custody, network readiness or mutation authority. Truncated/malformed
inventory remains terminal. Once the exact target exists, the existing target-bound
marker/binding/provenance checks remain unchanged and fail closed.

For today's unmarked IPv4, first obtain this sanitized observation on accepted
main. If provenance remains unproved, stop. Do not request keys, addresses, account
IDs or DSNs in chat, purchase another IP, delete it, or stamp a guessed association.
A later bounded reconciliation needs provider-verifiable custody or separate
explicit OWNER allocation authority, plus its own accepted contract. This repair
does not grant that authority. Unbound addresses continue to be billed by Timeweb;
"free" means unattached, not zero-cost. No additional purchase is authorized here.

Only after source acceptance and the relevant custody disposition is resolved may
one new main-bound manual transport verification run proceed. The required result
remains `TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=READY`; RU-PG-B SQL parity and RU-PG-C remain
separate and locked until their prerequisites are proved.

Provider schema references checked on 2026-09-20:

- https://github.com/timeweb-cloud/sdk-python/blob/main/docs/CreateFloatingIp.md
- https://github.com/timeweb-cloud/sdk-python/blob/main/docs/UpdateFloatingIp.md
- https://github.com/timeweb-cloud/sdk-python/blob/main/docs/FloatingIp.md
- https://github.com/timeweb-cloud/sdk-python/blob/main/timeweb_cloud_api/api/floating_ip_api.py

## Live RED #5 — combined public IPv4 + TLS transition rejected

Manual workflow ordinal #5 on exact protected main
`7a87509258552db4b9ee0c2e762597e561a42fb6` passed the exact-main/source gate,
explicit verifier `/32` validation, GitHub Environment policy, cost confirmation
and durable allocation prerequisite. The provider inventory was already
`managed_unbound=1 unproven_unbound=0`, so OWNER input, verifier CIDR and
existing-IPv4 custody were not the failing boundary.

The provider then rejected the database v2 mutation with:

`TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=STOPPED code=TIMEWEB_DATABASE_PUBLIC_NETWORK_PATCH_REJECTED http_status=400`.

The exact provider validation message is intentionally unavailable because the
mutation adapter does not read/log HTTP error bodies. Do not infer a hidden
provider message from the status alone. The bounded conclusion is that the
repository attempted an atomic transition that combined first-time public IPv4
attachment/enablement with `is_secure_connection_enable=true`, while current
Timeweb documentation requires public-IP connectivity before TLS is enabled.

The repair therefore splits the transition:

1. PATCH only the existing floating IPv4 plus public IPv4 enabled / IPv6 disabled;
2. GET-reconcile cluster state and exact managed-IP binding;
3. re-prove the DROP TCP/5432 verifier-only firewall and exclusive resource link;
4. PATCH only `is_secure_connection_enable=true`;
5. wait for secure connection plus issued technical domain;
6. re-prove firewall, binding and TLS `verify-full`.

A failure at either provider transition remains operation-specific and enters the
existing public-network rollback path. Blind mutation retry remains forbidden.
The existing IPv4 is reused; this repair grants no new purchase/delete authority.

Official Timeweb evidence rechecked on 2026-09-26:

- the public-IP guide describes enabling public IPv4 and selecting an existing
  account IP before adding it to the database;
- the PostgreSQL connection guide states that public-IP connectivity must be
  configured before enabling TLS;
- the generated `UpdateClusterV2` schema exposes public-network/floating-IP and
  secure-connection fields as optional partial-update fields on the same v2
  endpoint, allowing the two state transitions to be sent separately.

Do not rerun the live transport until this source repair is exact-head certified
and accepted on protected main.

## Live RED #6 — TLS/domain readiness outlived the fixed 83-second waiter

After PR #588 was accepted as protected main
`86294ebb0e5b6eb0a56aa8d4b28f1692f483a8d8`, manual workflow ordinal #6
passed the exact-main/source gate, verifier `/32`, GitHub Environment, cost
confirmation and existing-IPv4 allocation prerequisite. The prior deterministic
HTTP 400 did not recur.

The run then stopped with:

`TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=STOPPED code=TIMEWEB_PUBLIC_IPV4_TLS_READY_TIMEOUT`.

This marker can only be emitted by the GET-only network/TLS readiness waiter after
the public-IPv4 transition path has been entered. The source allowed only
`2+3+5+8+15+20+30 = 83` seconds before declaring timeout. Timeweb's API contract
explicitly permits a successful mutation response while the resource remains in a
startup/transition state, and the PostgreSQL TLS guide requires waiting for setup
completion without documenting an 83-second readiness SLA.

The repair therefore preserves exactly one mutation per transition and changes only
reconciliation behavior:

1. keep the public IPv4 and TLS PATCH operations separate;
2. keep post-mutation waiting GET-only with no blind mutation retry;
3. give TLS/domain/certificate readiness a bounded multi-minute budget that remains
   below the workflow timeout;
4. on timeout, emit a sanitized predicate-specific code distinguishing public-network
   drift, secure-connection enablement still pending, certificate/domain issuance
   still pending, and an otherwise-ready TLS surface whose cluster status remains
   transitional;
5. retain unsafe-status immediate stops, exact managed-IP/firewall verification and
   fail-closed public-network rollback.

No second IPv4 purchase, IPv4 delete/stamp, wildcard firewall, DNS mutation,
production DB cutover or Telegram/public-user activation is added by this repair.

The blast-radius review also hardens the live transport against provider/control-plane propagation without weakening any semantic gate. DB control-plane `500`/network failures may be retried only as bounded GET observations; `domains=null` during TLS setup is treated as not-yet-ready rather than malformed terminal state; transient CA download and TCP/TLS socket transport may retry within bounded budgets; certificate verification failure stays terminal. Public-network rollback has its own longer GET-only closure proof, so a rollback request is never mistaken for a proven rollback.

The same failure class was reviewed across the later currently authorized Timeweb delivery controllers. P2 adopts a unique in-flight exact-SHA deploy instead of issuing another POST, P3 receives a production-only bounded PostgreSQL reconnect window, and P4/P5/P6 retry only transient read-only public probes. Wrong SHA, wrong security headers, auth/authorization errors, certificate failures, provider-state drift and tenant/security proof failures are not retryable. This is the project-wide rule: **retry observation, never authority; adopt exact intent, never replay an uncertain mutation**.

Three additional restart/live-state protections are mandatory in this repair. First, App Platform deploy-history consumers must exhaust provider pagination rather than treating the first 100 rows as the complete history. Second, every bounded rollback wait must observe state once more after its final backoff. Third, firewall rule/resource mutations and their GET reconciliation must finish before public exposure; every firewall verification after public IPv4 or TLS enablement is read-only. This prevents stale provider reads from being converted into duplicate mutations while still failing closed on any semantic or security drift.
The OWNER also reports that `omnicio.ru` is visible in the Timeweb domain panel after
being added manually, and no further manual domain configuration was performed. Treat that as
unverified pre-existing provider state only. It is not accepted evidence of DNS,
certificate issuance or TLS readiness and grants no create/overwrite authority.
The provisioner must continue to rely on sanitized provider GET state and must not
log the hostname.

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

Until that proof is accepted, no production database cutover is authorized and
RU-PG-C remains locked.

## Official references

- https://timeweb.cloud/docs/dbaas/dbaas-manage/public-ip-access
- https://timeweb.cloud/docs/dbaas/postgresql/connect-to-database
- https://timeweb.cloud/docs/firewall
- https://timeweb.cloud/docs/firewall/upravlenie-fajrvolom
- https://timeweb.cloud/docs/public-ip
- https://timeweb.cloud/docs/public-ip/create-public-ip
- https://github.com/timeweb-cloud/twc
- https://github.com/timeweb-cloud/sdk-javascript
- https://github.com/timeweb-cloud/sdk-go/blob/main/docs/PresetsDbs.md
- https://github.com/timeweb-cloud/sdk-go/blob/main/docs/DatabaseClusterDisk.md
