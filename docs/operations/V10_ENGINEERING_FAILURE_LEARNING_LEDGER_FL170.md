# FL-170 — Current-navigation regressions must follow accepted migration authority

Date: 2026-09-24  
WP / PR / reference: TIMEWEB-PLATFORM-CONSOLIDATION / V9C-A / PR #584 / exact head `b8883df905539c7fce2ef10904d5d913f8018618`

## Symptom

The authoritative Regression Shield passed lint, type, secret and security checks but
failed `tests/test_post_v9_repository_hygiene.py` because the test required current
navigation documents to keep saying `v9.0.0` and `controlled maintenance`.

## Root cause

The repository hygiene regression encoded the pre-Amendment-20 product model as a
permanent invariant. Amendment 20 changed that authority: V9 is now a migration source
for the single forward V10/Timeweb runtime, with legacy working-tree retirement after
replacement/parity/consumer/recovery proof.

The current navigation producers `.github/copilot-instructions.md`,
`CHANGELOG.md` and `docs/master-plan/README.md` also still contained portions of
the superseded parallel-V9 wording.

## Blast radius

Reviewed the failing regression and all four navigation sources it protected. Historical
V9 release sections remain valid evidence; only current-navigation semantics were
stale. Broker/Real-money flags, tenant/RLS boundaries, accepted V9 evidence and Git
history are unchanged.

## Corrective change

Update current navigation to describe V9 as a migration source and change the
regression to protect Amendment-20 semantics instead of preserving the obsolete
controlled-maintenance wording. Historical release records remain historical.

## Permanent prevention rule

Current-navigation tests must protect current accepted authority, not freeze a prior
program phase. When a later accepted amendment intentionally supersedes a current-state
model, update both the navigation producers and the regression in the same checkpoint.

## Dependency/tooling knowledge change

None.
