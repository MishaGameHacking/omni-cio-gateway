# Omni-CIO V10 — WP6 Execution Contract

Status: **AUTHORIZED / IMPLEMENTATION IN PROGRESS**  
Block: **C — Lenovo Omni-CIO Node / infrastructure**  
WP: **WP6 — OS identities and privilege separation**

## 1. WP identity

- Authorized by current program status: **YES**.
- Accepted `main` baseline: `6afacf8cd611a60dd17b8f77dc4c053d738602c2`.
- Prior Exit Gate: WP5 PR #251 squash-merged as `d0b80f91a434e93e5facb244a92b17b066ccdf2a`, post-merge Regression Shield #1435 passed, canonical status PR #252 then passed exact-head CI and post-merge Regression Shield #1436.

## 2. Purpose

Establish a Windows privilege boundary such that compromise of an ordinary GitHub CI job does **not** automatically imply access to a future real-money trading secret or arbitrary privileged runtime control.

## 3. Inputs and prerequisites

Authoritative inputs:

- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` — WP6 scope and Exit Gate;
- `docs/master-plan/OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `docs/architecture/V10_SECURITY_BOUNDARIES.md`;
- `docs/architecture/V10_SYSTEM_ARCHITECTURE.md`;
- `docs/operations/SELF_HOSTED_WINDOWS_RUNNER_SERVICE.md`;
- `docs/operations/V10_RELEASE_PROVENANCE_RUNBOOK.md`;
- `SECURITY.md` and the accepted V9 real-trading runbook.

WP6 begins from the accepted Windows 11 Pro / BitLocker / thermal/network node evidence established by WP5. No actual broker, Telegram or database secret is required or permitted for WP6 testing.

## 4. Existing implementation to reuse

- GitHub self-hosted service `omni-cio-ci` and labels `[self-hosted, Windows, X64, omni-cio-ci]` — reuse with narrower identity evidence, not replacement.
- `permissions: contents: read`, same-repository PR gate, `persist-credentials: false`, external CI venv and workspace cleanup — reuse as accepted CI controls.
- WP4 release-manifest/provenance contract — reuse as the future deployment identity authority.
- `scripts/check_ci_security_baseline.py`, repository boundary guards and Regression Shield — extend; do not create a parallel safety framework.
- Existing V9 `app:app`, read-only GPT Actions contract and money-authority kill switches — protected unchanged.

## 5. Allowed changes

WP6 may change only the domains needed for identity/privilege separation:

- `docs/architecture/V10_WP6_*`;
- `docs/operations/V10_WP6_*`;
- `infrastructure/windows/*wp6*`;
- `scripts/*wp6*` plus narrowly required CI/security guards;
- `tests/test_v10_wp6_*`;
- GitHub workflows only where required to collect sanitized WP6 evidence or remove identity/secret exposure from CI;
- canonical V10 status only after the WP6 Exit Gate is accepted.

## 6. Explicit non-goals

WP6 does **not**:

- provision any real broker/read/trading token, Telegram token, private database dump or private portfolio payload;
- add broker write methods or change `trading_methods=false`;
- enable margin, leverage, uncovered shorts, transfer or withdrawal authority;
- implement Ollama/Qwen/Cortex, Web, Telegram, broker HTML runtime, Guardian/Watchtower V10 runtime, database runtime, Docker/container bootstrap or updater runtime;
- replace `app:app`, deploy V10 or change current V9 production/recovery authority;
- execute arbitrary PR payload under a secret-bearing identity.

Secret values belong to WP8/later owning packages. WP6 establishes only the identity/ACL boundary they must use.

## 7. Interfaces and contracts

### `V10_WP6_IDENTITY_PRIVILEGE_CONTRACT` v1

Repository-controlled machine-readable policy defining allowed identity classes, secret names forbidden to CI, deployment provenance rules and negative permission requirements.

### `WP6_IDENTITY_PROFILE` v1

Privacy-safe local evidence generated on the Lenovo node. It may contain role classifications and booleans only. It must not emit usernames, SIDs, hostnames, device IDs, IP/MAC addresses, tokens, secret values, process lists or private file contents.

Unknown/unavailable evidence is fail-closed for the Exit Gate.

## 8. Data/persistence effects

- Application/database migration: **NO**.
- GitHub stores only policy, code, tests and sanitized role-state evidence.
- Any local WP6 sentinel is explicitly **non-secret** and exists solely to prove ACL denial.
- Actual secret values remain outside GitHub and are not needed for acceptance.

## 9. Security / authority effects

WP6 changes OS/runtime privilege boundaries but does not change financial authority.

Target roles:

1. **OWNER admin** — human break-glass/provisioning authority; not a CI identity.
2. **GitHub runner** — existing self-hosted CI service identity; must be non-admin, distinct from the interactive OWNER identity and unable to read the protected real-money secret sentinel.
3. **Omni-CIO runtime** — dedicated non-admin local identity anchor for ordinary Core/Web/AI-side runtime work; no access to the real-money execution secret boundary.
4. **Omni-CIO execution** — dedicated non-admin identity anchor for the future isolated execution service; the only non-admin role allowed to receive read access to the execution-secret sub-boundary when WP8/later provisions real values.

Using a dedicated execution identity is required by the Master Plan statement that the execution service receives only the broker/network privileges it needs, and by the security boundary that AI/Web/Telegram must not inherit broker-write credentials.

## 10. Normal-path acceptance tests

- policy/schema validation succeeds;
- self-hosted runner service identity is classified without logging its raw account name;
- runner identity is non-admin and distinct from the interactive OWNER identity;
- ordinary runtime and execution identity anchors exist, are distinct, and are not Administrators;
- protected execution-secret sentinel exists and contains no real secret;
- runner read attempt against the sentinel is denied;
- ordinary runtime identity has no effective read access to the execution-secret sentinel;
- ordinary runtime identity has no effective write/modify access to GitHub runner configuration;
- CI workflows contain no reference to production secret contexts for real trading, Telegram or private DB material;
- deployment policy accepts reviewed release identity only and explicitly forbids arbitrary PR worktree execution in a secret-bearing context.

## 11. Negative/failure tests

Mandatory fail-closed cases:

- runner can read the execution sentinel -> **FAIL**;
- runner is LocalSystem/Administrator -> **FAIL**;
- runner identity matches the interactive OWNER identity -> **FAIL**;
- runtime/execution identity missing or Administrator -> **FAIL**;
- runtime can read execution sentinel -> **FAIL**;
- runtime can modify runner configuration -> **FAIL**;
- workflow references a forbidden production secret -> **FAIL**;
- AI/runtime policy permits direct broker-write credential/tool access -> **FAIL**;
- deployment source is arbitrary PR/worktree instead of reviewed release identity -> **FAIL**;
- malformed, partial or privacy-unsafe evidence -> **FAIL**.

No test uses a real secret. A fixed non-secret sentinel is sufficient to test ACL authority.

## 12. Observability and privacy

Allowed evidence:

- service running/start-mode state;
- account class (`NETWORK_SERVICE`, `LOCAL_SERVICE`, `LOCAL_SYSTEM`, `VIRTUAL_SERVICE`, `LOCAL_OR_DOMAIN_USER`);
- admin/distinctness booleans;
- ACL test outcomes (`PASS`, `FAIL`, `NOT_CONFIGURED`, `UNKNOWN`);
- workflow/static policy results.

Forbidden evidence:

- raw account/user names beyond repository-defined role names;
- SIDs;
- hostname/device IDs;
- addresses;
- secret values or hashes of secret values;
- private DB/portfolio content;
- process lists.

## 13. CI routing

- Fast hosted checks: schema/static policy/unit tests.
- Hosted Windows compatibility: PowerShell syntax/contract compatibility where routed by the accepted V10 CI router.
- Lenovo authoritative checks: privacy-safe identity collector and real ACL negative tests.
- GPU AI eval: **NO**.
- Release/recovery matrix: **NO** for WP6; WP4 release identity is reused as a policy prerequisite.

A red WP6 local identity/ACL audit is evidence of an uncompleted local boundary, not permission to weaken the policy.

## 14. Rollback / recovery

Before any later mutating provisioning step:

- record existing ACLs for only the WP6-owned local paths;
- never alter broker/portfolio data;
- never delete the GitHub runner registration as a shortcut;
- preserve an owner-admin recovery path;
- make account/ACL provisioning idempotent and reversible.

The initial audit phase is read-only and therefore requires no rollback.

## 15. Exit Gate

WP6 is **PASS** only when deterministic repository policy plus authoritative Lenovo evidence prove all of the following simultaneously:

- ordinary CI runner is non-admin and distinct from OWNER/runtime/execution identities;
- CI runner cannot read the protected execution-secret sentinel;
- ordinary runtime cannot read the execution-secret sentinel;
- ordinary runtime cannot modify runner configuration;
- execution identity is non-admin and is the only non-admin identity authorized for the execution-secret boundary;
- workflows cannot reference the forbidden real-money/Telegram/private-DB secret set;
- AI/general runtime has no direct broker-write secret/tool authority;
- deployment control remains bound to reviewed release identity rather than arbitrary PR payload;
- all existing Regression Shield, `app:app` and money-authority invariants remain green.

Equivalent statement: **compromise of an ordinary CI job does not automatically imply access to a real-money secret.**

## 16. Required acceptance evidence

- exact-head Fast PR, Toolchain Compatibility and authoritative Lenovo CI run IDs;
- sanitized WP6 identity profile;
- negative ACL permission results;
- static workflow-secret/deployment-policy tests;
- no unresolved review blockers;
- squash merge SHA;
- successful post-merge Regression Shield on that exact `main` SHA.

## 17. Documentation/status updates

The implementation PR must include this execution contract and operating/provisioning documentation. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` changes to `WP6 COMPLETE` only after the Exit Gate and post-merge Regression Shield succeed.

## 18. Next WP unlock

Only the next WP explicitly listed by the canonical Master Plan may start after WP6 acceptance. No adjacent infrastructure/runtime package is silently pulled into WP6.

## 19. Scope-discovery rule

Discovered work is classified as current-WP blocker, future-WP backlog, or OWNER-required program amendment. It is never implemented merely because it is nearby.