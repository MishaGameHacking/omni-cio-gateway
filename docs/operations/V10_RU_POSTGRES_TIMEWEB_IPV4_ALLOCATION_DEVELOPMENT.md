# RU-PG-B existing IPv4 allocation - source integration

Owning issue: #559. Execution unit: FOCUSED_CHANGE.
Base: `3083e65f9e6dbc7a6f26de6649ae7ff40627ba5c` (accepted PR #574).
This document describes a branch checkpoint, not another program-status ledger.

## Observed defect and authority

Public IPv4 TLS #3 / run `35527766579` stopped with
`TIMEWEB_IPV4_ORPHAN_PROVENANCE_REQUIRED`. Read-Only Proof #6 / `35527611769`
already reported the blocked disposition. The inventory was one unbound row,
zone-compatible and without DDoS, but with no matching management association.
The counts do not establish that the comment is empty or prove who created it.
The current unknown-resource refusal is correct; do not remove it.

The missing transition is explicit assignment of an existing resource, not a
retry, TLS or formatter fix. Generic development approval, an earlier cost
confirmation, a source merge and successful read-only observation do not assign
that resource. An exact live plan and separate OWNER decision remain required.
No provider writes, purchases, attachment, deletion, source authority migration,
product activation or production DSN changes occur when this source is tested.

## Checkpoint boundary and next milestone

M1 contains the allocation protocol, a concrete transactional SQLite journal,
CurrentUser DPAPI/Windows ACL custody adapter and GitHub OWNER-comment verifier.
The native custody boundary must be certified on the trusted Windows runner
before M2 wires provider credentials or an operational PLAN/APPLY/RECONCILE job.
This is the security/toolchain verification boundary, not permission to substitute
test doubles for production dependencies. One focused branch owns both milestones;
no competing branch or temporary verifier PR is needed.

M1 is SOURCE_CHECKPOINT_NATIVE_CERTIFICATION_PENDING, not INTEGRATION_READY for
live allocation. The contract distinguishes source adapter existence from their
production integration/acceptance. No executable provider entry point or new
workflow is included at this checkpoint. After exact-head M1 certification,
finish M2 on the same branch and repeat exact-head certification before landing.

## Protocol and reuse

The accepted `scripts/timeweb_ipv4_custody.py` remains unchanged. Its strict
inventory parser and exact v1 marker construction are reused, not replaced.

`prepare` requires two identical complete snapshots. Only one unbound IPv4,
EMPTY comment, MSK-1, no DDoS, exact target, public network OFF and IPv6 OFF are
eligible for a plan. Private context includes provider scope, project, cluster,
resource identity, address, source, previous state and one-hour expiry. Public
output contains only a random non-authorizing plan handle. The private checksum
is an integrity comparison within authenticated custody, not an authorization.

`apply` requires independent plan-bound OWNER evidence and the distinct
`ALLOCATE_EXISTING_TIMEWEB_IPV4_NO_CREATE_NO_DELETE` confirmation. It checks
expiry/revocation, two fresh snapshots and current main, atomically claims the
plan, rereads the claim, and rechecks source/approval/resource before the only
metadata write. The writer can change comment only. No create/delete/bind/TLS
operation is part of this protocol. Two matching GETs plus a saved journal receipt
are required before ALLOCATED_VERIFIED.

`reconcile` accepts no provider writer. An ambiguous attempt stays ATTEMPTED even
past expiry, and replayed APPLY is forbidden. Reconciliation uses provider GETs
and can complete a receipt. It does not purchase, rewrite, delete or enable
networking. Source drift requires a separate recovery review rather than silently
applying old plans under new source authority.

## Concrete closed-journal source

SQLite is used solely as a local engineering-operation journal on the existing
trusted Windows verifier. It is NOT a new application database, tenant store,
Gateway, production origin or substitute for Neon/PostgreSQL.

The fixed runtime location is below LOCALAPPDATA/OmniCIO/TimewebIpv4AllocationV1,
outside the disposable Actions workspace. APPLY cannot initialize a missing
store. Only initial journal provisioning may create it; an existing empty or
invalid store is rejected. No private values appear in file names or SQLite keys.

Each payload is sealed with Windows CurrentUser DPAPI, which provides encryption
and integrity checking. No new encryption key is requested from OWNER. The
non-interactive flag is required; machine-wide decryption is not enabled. The
SQLite main and rollback files contain ciphertext, not private plan JSON. The
random public handle is the primary key. The decoded payload must bind that handle
and pass the protocol validators.

The directory is created with a protected ACL for the current Windows identity
and SYSTEM. Existing loose ACLs are rejected rather than silently repaired.
Reparse points, unexpected children and locations inside GITHUB_WORKSPACE are
rejected. ACL/location evidence is rechecked before each transaction.

`BEGIN IMMEDIATE` serializes claims across independent connections. DELETE journal
mode and synchronous=EXTRA are required and checked. A successful durable COMMIT
must precede the provider call. Expired unattempted plans may be superseded but
not overwritten; ATTEMPTED and ALLOCATED conflicts remain blocked. Record count is
bounded. Lost acknowledgements, invalid ciphertext, malformed records and failure
to persist an allocation receipt remain STOPPED.

This protects against process restart and concurrent callers under the trusted
runner/storage model. It does NOT prove safety against a compromised Windows
identity, a malicious provider administrator, arbitrary restoration of an old
database, loss of the entire runner profile, or storage hardware that ignores
sync. Do not restore or delete the journal to clear a claim. Runner replacement,
total journal loss or backup restoration needs explicit reconciliation before
any APPLY; a copied old journal is not a new authorization. Native CI is not a
physical power-loss test. No global exactly-once guarantee is claimed.

## Concrete OWNER evidence source

The GitHub verifier reuses the accepted bounded GET/no-redirect HTTP transport
from `verify_v10_timeweb_github_environment.py`. It fetches repository ownership,
the exact issue #559 comment and current main on each verification. It accepts
only an unedited User comment whose numeric identity and login match the current
personal-repository owner and whose author association is OWNER.

`performed_via_github_app` must be explicitly null. Missing attribution, bots and
connector/app-authored comments are rejected even when attributed to OWNER.
The exact body binds the random plan handle, source SHA, expiry and the
NO_CREATE/NO_DELETE/NO_NETWORK_ENABLE purpose. The closed journal prohibits plan
replacement, binding the handle to the private digest without publishing it.

Revocation means editing or deleting that exact approval comment. A separate
unrelated comment is not an implemented revocation channel. The verifier refetches
evidence immediately before the write and does not cache approval. GitHub account
identity is not a claim of physical presence or MFA. Owner credentials and the
trusted runner remain part of the trust boundary. Cross-service revocation cannot
be atomic with a Timeweb write, so external writers must remain frozen during the
bounded operation and observed drift always blocks it.

GitHub Environment access alone is not OWNER approval. Required deployment
reviewers have private-repository plan restrictions. No new permissions are
introduced by M1; M2 must explicitly review the minimal read scope for issue
comments before an operational job can use this verifier.

## Executed proof and remaining acceptance

Local Python 3.13.5 executes 89 focused scenarios: 88 pass and the explicit
Windows-only DPAPI/ACL case is not applicable in Linux. The original 68 protocol
and guard scenarios are preserved; the new tests exercise real SQLite restart,
independent-connection claim contention, ciphertext corruption, transaction
failure, expiry, approval scope, connector rejection and revocation checks.
The local reversible codec is test-only and is not encryption evidence.

On Windows, the native test must actually execute DPAPI sealing/unsealing, tamper
rejection, private values absent from database bytes, ACL checks and reopening the
real protected store. A Linux skip does not certify that requirement. Production
GitHub/provider credentials and actual OWNER approval are not used in tests.

Before publication the changed Python must compile/parse for Python 3.12, the
source contract and focused tests must pass, and the complete changed surface
must be reviewed for secret/authority expansion. Canonical Ruff 0.16.1, mypy,
repository-wide tests/coverage, dependency/security checks and exact-head
Sonar/Gitar/review remain mandatory remote certification when approved local
executables or full checkout are unavailable. No alternate tool result is labeled
equivalent; no lock or check is weakened. CI failures require one coherent repair
of the observed defect set, not unrelated feature advancement.

## M2 source integration and acceptance before any live plan/application

M2 source now includes the canonical Timeweb complete-snapshot/comment-only
adapter, protected-main INITIALIZE/PLAN/APPLY/RECONCILE runner and workflow,
provider-secret/control-plane guard integration, minimal APPLY-only issue-read
permission, and safe summaries that explicitly stop short of transport readiness.
The workflow shares the existing Timeweb network/TLS concurrency group so metadata
allocation and network mutation cannot race. PLAN and RECONCILE construct a
read-only provider; APPLY alone constructs the comment writer after the durable
claim and fresh OWNER/source/resource rechecks performed by the M1 protocol.

The provider adapter reuses the accepted bounded Timeweb GET and mutation
transports. It requires the exact project/cluster shape, public network OFF,
IPv6 OFF, one complete floating-IP row, matching list/detail state, no PTR,
EMPTY comment and the accepted custody-v1 marker preimage. The only provider
mutation exposed by this subsystem is one PATCH of the selected floating IP's
comment field. No create/delete/bind/unbind, firewall, network-enable, TLS or SQL
operation is part of allocation.

This source state is still branch-local and requires new exact-head
Ruff/mypy/tests/security/Sonar/review certification. It is not live allocation
acceptance. After source acceptance, INITIALIZE provisions the protected
persistent journal without provider access; PLAN is read-only and emits only the
non-authorizing handle plus exact OWNER-comment template; APPLY still requires a
fresh direct OWNER comment bound to that plan and the exact allocation
confirmation; RECONCILE is GET-only. Only after post-merge verification may a
real PLAN be generated. Do not run the current paid transport workflow while
allocation remains unresolved.

After allocation is independently verified, reuse the existing exclusive DROP
firewall / one verifier /32 TCP/5432 / hostname-verified TLS path. Preserve the
pre-existing resource during network rollback. Allocation verification is not
transport READY or SQL parity PASS. RU-PG-C, production cutover, public auth,
broker-write, trading_methods and REAL_TRADING_ENABLED remain locked.

## Primary references

- https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
- https://sqlite.org/pragma.html#pragma_synchronous
- https://sqlite.org/atomiccommit.html
- https://docs.github.com/en/rest/issues/comments#get-an-issue-comment
- https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
- https://timeweb.cloud/docs/public-ip

## M1 independent review findings and repair

Initial source head `8c845b5...` reached Governance #1758 / run `35531378453`.
Its exact-head external review gate rejected seven Sonar findings in exception
assertions. These were ambiguous test boundaries: parsing/constructing a context
or reopening a journal occurred inside the same assertion as the operation under
test. An exception in setup could therefore satisfy the assertion without proving
the intended refusal. The affected operations are allocation selection, source
drift, journal conflicts, superseded claims and unknown plan reads.

The correction moves all such setup outside the exception assertion. It preserves
every tested exception and postcondition and adds an AST regression checking that
these exception assertions contain exactly one possible invocation. Focused tests
exercise the corrected modules; independent exact-head Sonar is still required.
The local preflight had not included this test-structure property or Sonar's rule;
the new regression prevents copying the same pattern within this subsystem.
No source guard, security check or approval requirement is suppressed.

The independent Windows authoritative run #2973 / `35531378435`, job
`106132465885`, then passed locked dependencies, PostgreSQL 18 runtime-role
rehearsal, repository/security boundaries, compilation and Ruff lint. Canonical
Ruff 0.16.1 formatting rejected one list-comprehension wrapping in
`timeweb_ipv4_allocation_journal.py`. Applied the exact formatter-reported change;
the formatting-only old/new ASTs are identical. Mypy, full tests, native DPAPI/ACL,
coverage and later security scans were NOT reached in that failed run.

Adjacent static-gate inspection found that pyproject.toml enumerates mypy targets
explicitly and did not yet include these five new modules. Add all five targets
without removing any baseline target or changing any option/lock. A regression
pins their inclusion. The DPAPI description temporary is explicitly annotated
`str | None` to represent both native call variants. This expands static coverage;
it is not a toolchain version change or a suppression of type errors.

Correction preflight executes 91 focused scenarios on Python 3.13.5: 90 pass and
the Windows-only case is not executed on Linux. The assertion-shape regression
also rejects an injected nested-call mutation. Python 3.12 grammar/compilation,
source contract and TOML validation pass. Whole correction review confirms that
existing tests/security assertions, dependency locks, live flags, database and
provider permissions remain unchanged. Approved local Ruff/mypy and the full
repository are still unavailable; the exact replacement head requires new
canonical CI evidence, including real native Windows execution, before M2 work.
