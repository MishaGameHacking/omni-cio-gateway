# V10 Engineering Failure Learning Ledger — FL074

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, exact-head verification on PR #413 after the CF-D secret-scan correction.

This entry records a transient external registry failure that turned one deterministic Web security gate RED even though the product build and browser evidence had completed successfully. It does not authorize merge, production cutover, public multi-user activation, broker write, or Real execution.

## Exact failure evidence

Exact head `efff5fe6917d23525383a2a7c3693ff3faa53d7d` ran `V10 WP19 Watchtower Incident Audit` in workflow run `33421660623`, job `99585256915`.

Before the failure, the job successfully completed:

- exact reviewed repository bootstrap;
- protected Python and Node toolchain bootstrap;
- hash-locked Python dependency installation;
- committed Web lock reproduction;
- Web type-check and lint;
- 66 Web unit tests;
- production Web build;
- 22 Playwright incident-lifecycle browser tests.

The only failing stage was `Audit Web dependencies`. npm attempted its registry security advisory request and reported:

`Client network socket disconnected before secure TLS connection was established`

followed by `audit endpoint returned an error`. The workflow then exited with its existing audit failure code `36`.

No dependency vulnerability was reported by that failed invocation. The failure was inability to obtain the remote audit response.

## Root cause

The Web security workflows treated `npm audit --audit-level=high` as a one-shot external operation. That is correct for vulnerability authority but incomplete for transport reliability: a transient registry/TLS interruption immediately failed the complete gate even when a retry could safely re-read the same advisory metadata.

The defect is therefore not that the audit was mandatory. The defect is that mandatory remote security metadata retrieval had no narrowly bounded transport-fault recovery policy.

Security semantics must remain fail-closed:

- a real npm audit vulnerability/non-transient failure must fail immediately;
- an unknown failure must fail immediately;
- only positively classified transient registry/transport failures may retry;
- exhausted retries must remain RED;
- success may only come from an actual successful npm audit invocation.

## Blast radius searched

Repository search found the same direct one-shot high-severity npm audit pattern in ten active Web CI consumers:

1. `v10-pr-fast-checks.yml`;
2. `v10-wp15-live-web-support-audit.yml`;
3. `v10-wp16-web-design-system-audit.yml`;
4. `v10-wp17-application-shell-audit.yml`;
5. `v10-wp18-portfolio-dashboard-audit.yml`;
6. `v10-wp19-watchtower-incidents-audit.yml`;
7. `v10-wp20-research-dossier-audit.yml`;
8. `v10-wp21-decision-risk-plan-audit.yml`;
9. `v10-wp22-system-admin-audit.yml`;
10. `v10-wp22a-clientless-access-audit.yml`.

Fixing WP19 alone would leave nine directly analogous failure paths, so this correction is applied to the defect class rather than a single symptom.

## Corrective change

1. Add `scripts/run_v10_npm_audit.py`, a dependency-free wrapper around the mandatory high-severity npm audit.
2. Default to three total attempts with bounded increasing backoff.
3. Retry only recognized transient registry/network signatures, including the exact observed TLS failure and standard reset/timeout/name-resolution/temporary HTTP failure classes.
4. Preserve the original npm audit exit status for vulnerability/non-transient failures and after transient retry exhaustion.
5. Route all ten current Web audit consumers through the wrapper without changing their existing workflow-level failure codes.
6. Add `scripts/check_v10_npm_audit_policy.py` so all protected Web audit workflows must use the wrapper and raw one-shot audit commands are rejected repository-wide.
7. Extend `tests/test_v10_regression_shield.py` with deterministic regression cases for the observed TLS break, successful transient recovery, non-retry of security findings, fail-closed exhaustion, and one-shot-workflow rejection.
8. Keep the audit threshold at `high`; do not use `continue-on-error`, broad suppression, audit disablement, or vulnerability allowlisting.

## Why prior preflight missed it

The prior checks proved the ordinary audit path, but they did not simulate a remote advisory endpoint transport failure. The repository already used bounded retry for Git repository bootstrap transport, showing the accepted reliability pattern existed, but that pattern had not been extended to the npm advisory retrieval boundary.

A deterministic fault-injection unit test now covers the transport classifier and retry state machine before an expensive full workflow reaches the external registry.

## Permanent learning

- Mandatory security gates may use bounded retries for positively identified read-only external transport failures without weakening the security decision.
- Retry policy belongs around transport acquisition, never around a confirmed vulnerability result.
- A security gate must not convert network exhaustion into success; no remote evidence means the gate remains RED.
- When one CI defect is caused by a shared invocation pattern, search and correct every directly analogous producer/consumer instead of patching the first failing workflow.
- Add deterministic fault-injection coverage for external CI dependencies whose transient failure can invalidate an otherwise complete build.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- Telegram/VK activation remains outside this correction.
- Broker write remains OFF.
- `trading_methods=false` remains unchanged.
- `REAL_TRADING_ENABLED=false` remains unchanged.
- No provider, broker, database, or account secret is added to source, logs, comments, or artifacts.
- No Cloudflare production mutation is performed by this correction.
