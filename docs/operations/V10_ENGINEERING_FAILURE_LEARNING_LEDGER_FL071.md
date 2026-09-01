# V10 Engineering Failure Learning Ledger — FL071

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, exact-head verification after real CF-C staging acceptance.

This entry records the remaining verification findings on exact head `6c81095ca2a0da188b557f2e1a0283bd57519ad9`. It does not authorize CF-D, public cutover, multi-user activation, broker write, or Real execution.

## Exact failure evidence

The exact head proved the real CF-C provider path first:

1. Cloudflare provider readiness passed;
2. Workers Builds and Containers registry authority passed;
3. isolated Neon staging provisioning passed as `omni_cio_cloudflare_staging`;
4. the gated exact-SHA Worker + Container build passed;
5. the live release endpoint matched the exact source SHA;
6. container-backed health converged and passed;
7. staging-trigger quarantine and self-hosted cleanup passed;
8. no production promotion occurred.

The same exact head then exposed two separate verification classes:

- `Self-Hosted Windows CI / V10 authoritative merge gate` reached protected static quality and failed only because Ruff reported `scripts/run_v10_cloudflare_gated_candidate.py` would be reformatted. `ruff check` itself passed.
- `V10 WP21 Decision Risk Plan Audit` failed before checkout because Git for Windows/Schannel could not complete the HTTPS/TLS handshake with GitHub on all three bounded exact-SHA fetch attempts.

Independent Sonar review also reported three test-quality findings in `tests/test_v10_cloudflare_runtime_database_role.py`: connection-object construction occurred inside `assertRaisesRegex` contexts, allowing setup exceptions to be mistaken for the one exception the test intends to assert.

## Root-cause separation

### A. Source formatting defect

The FL070 correction changed the CF-C orchestration import after earlier formatting work, but the final file was published without applying the repository-pinned Ruff formatter to that exact source state. The defect is source-local and deterministic.

### B. WP21 transport interruption

The WP21 failure is not a product/source regression. The accepted self-hosted bootstrap contract already performs exactly three clean, bounded, non-interactive read-only fetch attempts, removes partial `.git` state and temporary credential helpers between attempts, verifies the exact SHA after success, and remains RED after exhaustion.

A targeted rerun of the same workflow on the unchanged exact head completed the repository bootstrap successfully and then completed the full WP21 gate successfully. This proves that changing product source or weakening the retry boundary is not warranted for this occurrence.

GitHub's current self-hosted-runner documentation continues to require outbound HTTPS connectivity over port 443 from the OWNER-managed runner host. The observed Schannel handshake failure is therefore retained as infrastructure evidence rather than converted into synthetic GREEN.

### C. Test exception-boundary quality defect

The three Sonar findings share one test-structure root cause: object construction and the target runtime probe call were in the same `assertRaisesRegex` context. The tests still asserted the intended failure codes, but an unrelated constructor exception could have satisfied the context incorrectly.

## Blast radius

- Formatting: the current CF-C orchestration module only; repository-wide Ruff formatting remains the authoritative guard.
- Transport: any self-hosted workflow using the accepted exact-SHA Git bootstrap can experience a genuine external TLS interruption. The repository-wide resilience contract already owns this defect class and must not be weakened or silently extended into unbounded retries.
- Test structure: negative tests that construct helpers inside exception assertions. The current correction removes the three findings identified on the new Cloudflare runtime-role tests without suppressing Sonar.

## Correction

1. Apply the repository-pinned Ruff formatting shape to the CF-C quarantine import.
2. Move each runtime-role test connection construction outside `assertRaisesRegex`; keep only the target `_probe_cloudflare_runtime_database(...)` invocation inside the exception context.
3. Keep the WP21 bootstrap implementation unchanged because the same exact head reran successfully and the accepted three-attempt fail-closed contract behaved as designed.
4. Do not disable TLS verification, do not add unbounded network retries, do not convert exhausted transport failure to success, and do not broaden credentials.
5. Re-run every applicable check on the new exact head because this correction commit invalidates final evidence from `6c81095...`.

## Why prior preflight missed it

The runtime-role correction was validated functionally and by provider acceptance, but the exact final orchestration source state was not run through Ruff formatting before publication. The negative tests were functionally deterministic, but the preflight did not apply the independent-review rule that exception assertions should contain only the intended throwing invocation.

The transport failure was not predictable from source preflight: it occurred before checkout at the external GitHub HTTPS boundary and disappeared on an unchanged-head rerun.

## Permanent learning

- Apply formatter verification to the exact final changed-file state immediately before publishing a correction commit, not to an earlier intermediate state.
- For exception tests, instantiate fixtures/connections before entering the exception assertion context unless construction itself is the behavior under test.
- Treat self-hosted Git/TLS exhaustion as truthful infrastructure RED. Use the repository's existing bounded retry and one same-head rerun for diagnosis; modify the bootstrap contract only if repeated evidence proves a systemic contract defect.
- Independent review findings remain actionable even when the aggregate quality gate passes.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- Telegram/VK activation remains outside this correction.
- Broker write remains OFF.
- `trading_methods=false` and `REAL_TRADING_ENABLED=false` remain unchanged.
- No provider/broker/database secret value or full private identifier is added to source or logs by this correction.
- No CF-D production mutation occurs in this correction.
