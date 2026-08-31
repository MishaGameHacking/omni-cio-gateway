# V10 Engineering Failure Learning Ledger — FL066

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, gate CF-C LIVE.

This entry records the exact-head build-log pagination defect exposed after FL065 made failed Workers Builds diagnostics observable. It does not grant CF-C acceptance and does not authorize CF-D.

## Failure

On exact head `8f7ada2e40ad061b7538b408e26caa24e4f60888`:

1. Workers Builds authority, repository connection, build-token authority, staging database secret custody and the staging trigger all passed their provider checks.
2. The candidate reached a real Cloudflare Workers Build and the build terminated with failure.
3. Failed-build diagnostics then stopped at `CLOUDFLARE_BUILD_LOG_CURSOR_INVALID` instead of classifying the build failure.
4. The authoritative Windows merge gate independently rejected the same head because `ruff format --check` found one deterministic formatting drift in the failed-build log retry print statement.

The correct response is a source correction with deterministic pagination regressions and formatter compliance. Neither failure may be silenced, converted to success or bypassed.

## Root cause

Cloudflare's current Workers Builds API models the build-log response with optional `cursor`, optional `lines`, and optional boolean `truncated`. Its documented successful example may return a non-empty `cursor` while `truncated` is `false`.

The branch implementation treated every non-empty cursor as proof that another page had to be fetched. Therefore a terminal page carrying an advisory cursor could be fetched again. When the provider returned the same cursor, the duplicate-cursor safety guard correctly stopped the diagnostic path, but the pagination decision that reached that guard was wrong.

The pagination contract must be driven by `truncated is True`, not merely by cursor presence. A true truncation requires a valid, bounded, previously unseen cursor. A false or omitted truncation flag must not invent additional requests. If the bounded page budget is exhausted while pages remain truncated, diagnostics fail closed instead of classifying incomplete logs.

The formatter failure was independent and deterministic: the previous correction batch was published with a multiline print expression that the repository formatter canonicalizes to one line.

## Blast radius

- Every terminal CF-C Workers Build uses the same failed-build diagnostic helper, so the pagination defect could hide any provider build root cause when a terminal response included a cursor.
- Following cursors without the truncation signal can create redundant reads and false duplicate-cursor failures.
- Ignoring a true truncation would be equally unsafe because it could classify an incomplete log set. The correction therefore validates both the truncation flag and the required cursor for continuation.
- The formatter defect affects exact-head authoritative merge acceptance even when runtime logic is otherwise correct.

## Durable prevention

1. Treat `truncated is True` as the only pagination-continuation signal.
2. Require a non-empty string cursor within the repository size bound for every truncated page.
3. Reject repeated cursors and invalid truncation types deterministically.
4. Stop after a non-truncated page even if Cloudflare supplies a non-empty cursor.
5. Treat an omitted optional truncation flag conservatively as no pagination request rather than inventing provider work.
6. Fail closed with `CLOUDFLARE_BUILD_LOG_PAGINATION_EXHAUSTED` if the bounded page budget ends while pagination still requires continuation.
7. Preserve the narrow FL065 `404` log-readiness retry and sanitized diagnostics.
8. Add regression tests for terminal pages with cursors, encoded multi-page cursors, optional truncation, malformed truncation, invalid/repeated cursors, and bounded pagination exhaustion.
9. Run formatter/static quality before publishing the correction head.

## Security and authority invariants preserved

- Provider authority checks remain mandatory and fail closed.
- Build-log access remains read-only, bounded and scoped to a known build UUID.
- Provider response bodies, tokens, account identifiers, database credentials and private runtime data are not emitted.
- No production promotion is performed by this correction.
- `PUBLIC_MULTI_USER_ENABLED=false` remains protected until its authorized capability/CF-D gates.
- Telegram/VK provider activation remains disabled until real provider registration and evidence exist.
- `REAL_TRADING_ENABLED=false` remains protected.
- `trading_methods=false` remains protected.
- broker write remains OFF.
- CF-D remains blocked until CF-C exact-head candidate acceptance succeeds.

## External reference

Cloudflare's current Workers Builds API documents `GET /accounts/{account_id}/builds/builds/{build_uuid}/logs`, an optional cursor query parameter, and a response containing `cursor`, `lines`, and `truncated`. The documented successful response demonstrates that cursor presence alone does not establish that another page is required because a non-empty cursor can coexist with `truncated: false`.
