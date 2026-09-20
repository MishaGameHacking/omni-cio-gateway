# PR #574 - IPv4 custody checkpoint static-quality repair

Status: **BRANCH-LOCAL FAILURE LEARNING - NOT ACCEPTED MAIN AUTHORITY**
Date: 2026-09-20
Scope: RU-PG-B / issue #559 / PR #574
Canonical ledger: `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`.

## Symptom and exact evidence

Checkpoint `385f11f...` failed Engineering Governance #1754 (run
`35523148018`) and Self-Hosted Windows CI #2970 (run `35523148026`).
The Sonar check reported Quality Gate passed but three new findings: two numeric
regular expressions and a field named like its enclosing class. The repository's
zero-new-issues gate correctly rejected that result. Ruff lint passed; the
canonical formatter rejected one source-guard file. Mypy and the later complete
regression/security steps were not reached and are not certified by those runs.

## Root cause and preflight gap

The logical custody implementation had focused unit and dependency-isolated
preflight evidence, but the approved Ruff/Sonar-equivalent static-quality proof
was absent. Manual formatting missed quote/wrapping normalization. The regex
and dataclass naming patterns were introduced together without covering the
independent static-review constraints. Passing functional tests does not prove
formatting, naming, external-review acceptance or full integration.

## Blast radius and correction

Inspect both numeric validators, the custody record and all consumers of its
address field, marker construction, selection, receipt validation, restart
recovery and cleanup. Replace the digit class with `\d` while explicitly keeping
`re.ASCII`; accepting Unicode decimal digits would change provider identity
semantics. Rename the field to `ip_address` without changing positional layout,
provider JSON keys, the marker preimage or the evidence boundary. Apply the exact
formatter-reported quote/wrapping changes; the guard AST must remain identical.

## Permanent regression protection

`tests/test_v10_timeweb_ipv4_identity_regressions.py` covers canonical ASCII
identities, non-ASCII decimal digits, padding/type/length rejection, database
aliases, the fixed synthetic v1 marker preimage and private-evidence exclusion.
The existing custody/restart/no-extra-purchase/no-adoption/cleanup tests remain
unchanged. Existing exact-head Sonar and Ruff gates remain mandatory; no
suppression, relaxed threshold, dependency update or skipped assertion is added.

## Future prevention and proof limits

A formatter correction is proved by the approved formatter, not by visual
inspection alone. When that executable cannot run locally, record the limitation
and do not represent AST or isolated tests as full certification. Review all
findings together, check identity/security semantics before cosmetic changes,
and certify the replacement exact head before another functional checkpoint.

This repair's local proof comprises 41 actual custody-module tests plus seven
new tests using the exact numeric function extracted from the changed source;
its unchanged exception dependency is isolated in scratch preflight only. The
committed tests import the real repository modules. The scratch harness is not
committed. Canonical Ruff 0.16.1, full mypy, full tests/coverage, SAST, dependency
and secret checks still require actual repository execution. No alternate tool
version is declared equivalent and no lock is changed.

No live Timeweb mutation is performed by this source repair. The unidentified
unbound address remains subject to its separate provenance/allocation gate;
source certification is not permission to adopt, stamp or delete that resource.
