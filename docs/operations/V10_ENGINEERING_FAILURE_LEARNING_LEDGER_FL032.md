# FL-032 — Synthetic CI credentials must not be hard-coded in new code

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 4; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-22**  
WP / reference: **WP22A Phase 4 / PR #366 / SonarQube Quality Gate on exact head `845c70d6a6f4a8b3474626cd4f25187131bb09d0`**

## Symptom / failing gate

After the PostgreSQL 18 creator-admin semantics and hosted bootstrap were proven on real PostgreSQL 18, SonarQube Cloud rejected the pull request with **E Security Rating on New Code** while requiring rating A.

## Root cause

The new PostgreSQL 18 rehearsal embedded deterministic synthetic passwords in Python constants, and the two new CircleCI job definitions duplicated a synthetic PostgreSQL password/DSN literal already present in the established PostgreSQL lane.

Those values were not production secrets, but security analyzers correctly classify credential-shaped constants by representation and use, not by the developer's statement that a value is synthetic. A detector-specific allowlist comment is not a portable security boundary and does not make hard-coded credentials acceptable new code.

## Blast radius searched

The review covered:

- the new Phase 4 PostgreSQL 18 rehearsal;
- all new CircleCI Phase 4 PostgreSQL job definitions;
- database-role password construction and DSN generation;
- the existing PostgreSQL 18 lane used as the reusable isolation pattern;
- secret/logging controls and provider-deployment authority.

No production/provider credential, broker credential or private user data is introduced by the correction.

## Why preflight missed it

Preflight concentrated on preventing disclosure of real secrets and proving PostgreSQL 18 authorization semantics. It did not challenge whether deterministic synthetic credential literals would be treated as new-code vulnerabilities by the independent SonarQube policy.

## Corrective change

- generate rehearsal-only role passwords at runtime with `secrets.token_urlsafe(32)`;
- never print or persist those generated values;
- reuse the existing isolated PostgreSQL 18 CircleCI job through an enum parameter instead of duplicating service credential literals into two new job definitions;
- preserve separate job invocations, so each Phase 4 rehearsal still receives an isolated PostgreSQL service container;
- add deterministic source guards that reject restoration of the removed Python credential constants and require the parameterized isolated-job structure.

## Permanent regression / guard

`tests/test_wp22a_phase4_pg18_rehearsal_security.py` verifies ephemeral password generation and the non-duplicated CircleCI job topology. SonarQube remains an independent exact-head security gate and must return rating A before merge.

## Future prevention rule

Synthetic credentials are still credentials. When a test requires authentication, prefer runtime-generated ephemeral values and reuse an existing isolated CI service definition instead of adding credential-shaped literals to new source lines.

Do not suppress an independent security gate merely because another scanner has an allowlist for the same literal.

## Dependency/tooling knowledge change

Secret scanners and SAST engines classify source representation and dataflow independently. A comment accepted by one detector is not evidence that another detector will or should accept a hard-coded credential.
