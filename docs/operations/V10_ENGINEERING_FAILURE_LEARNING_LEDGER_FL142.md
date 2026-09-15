# V10 Engineering Failure Learning Ledger — FL142

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `RED_REPAIR_ONLY`
- Failure class: `PROVIDER_SECRET_CUSTODY_METADATA_TRIPS_TRACKED_CONTENT_SCANNER`
- Exact failing head: `3f6a7342720aae1968b4f482b529476e02b904b1`
- Scope: provider-secret custody contract/guard representation only

## Exact failure evidence

Fresh DRAFT exact-head certification for PR #511 completed twelve of thirteen repository workflows successfully. The only failing workflow was `Self-Hosted Windows CI` run `35008469996`, authoritative merge-gate job `104514109072`.

That job successfully completed:

- bounded Windows lock verification;
- repository/security/governance policy checks;
- compilation;
- Ruff lint and format checks;
- mypy;
- protected `app:app` verification;
- read-only GPT Actions contract verification;
- full Regression Shield (`3143 passed`, `326` subtests, branch coverage `62.20%`);
- dependency audit with no known vulnerabilities;
- Bandit SAST.

It then failed only at the mandatory tracked-content `detect-secrets` scan with five `Secret Keyword` findings:

- two scalar role-metadata fields in `docs/architecture/V10_PROVIDER_SECRET_CUSTODY_CONTRACT.json`;
- three internal constant declarations in `scripts/check_v10_provider_secret_custody.py`.

No credential value, provider token, database password, full private provider identifier, broker token, or private payload was present in those findings. They contained only repository secret **names** and authority-role metadata.

## Root cause

The new guard correctly models provider-secret names as metadata, but some source identifiers describing that metadata used detector-sensitive words such as `secret` or `api_key` while being assigned hard-coded string literals.

`detect-secrets` KeywordDetector intentionally treats those shapes as suspicious. This repository has already learned the same defect class in FL027 and FL073: a non-secret configuration/binding name can still be indistinguishable from a hard-coded credential to a lexical scanner when the source identifier itself looks credential-bearing.

The defect is therefore the source representation, not the scanner. Disabling KeywordDetector, adding broad exclusions, or allowlisting these lines would reduce detection strength and is forbidden.

## Blast radius and analogous-pattern review

The authoritative report contained exactly five findings, all inside the newly added provider-secret custody contract/guard. Directly coupled surfaces reviewed are:

- `docs/architecture/V10_PROVIDER_SECRET_CUSTODY_CONTRACT.json`;
- `scripts/check_v10_provider_secret_custody.py`;
- `tests/test_v10_provider_secret_custody.py`;
- the repository-wide `detect-secrets==1.5.0` tracked-content scan;
- prior FL027/FL073 source-representation guidance.

The actual GitHub Actions secret references and the nine-name provider inventory are not changed. Cloudflare/Neon credentials, provider identifiers, workflow authority, PostgreSQL role semantics, domain bindings, and the protected V9 runtime are outside the correction.

## Permanent correction

- Keep all nine repository provider-secret names and all workflow consumers unchanged.
- Rename only machine metadata keys from detector-sensitive `*secret*` role wording to `*binding*` wording where the value is a secret-name string.
- Rename internal Python constants that store secret-name strings to semantic `*_BINDING` identifiers while preserving their exact string values.
- Keep removed/deprecated secret-name strings in the policy because the guard must still reject those names in workflows.
- Add a deterministic source-level regression requiring detector-unambiguous role metadata and internal binding identifiers.
- Do not add `detect-secrets` exclusions, inline allowlists, baselines, plugin disabling, or weaker post-filter rules.
- Re-run the full exact-head certification because this source correction creates a replacement SHA.

## Prevention law

A secret **name** may be legitimate source-controlled metadata, but internal constants and scalar policy fields that hold such names must use representation that cannot be confused with a hard-coded credential by the repository's mandatory scanner. Prefer `*_BINDING`, `*_ENV`, or equivalent semantic metadata identifiers over assigning literals to `*SECRET*`/`*API_KEY*` identifiers.

For any new security/provider contract, focused preflight must include the same tracked-content scanner used by the authoritative gate whenever that tool is available. Scanner false positives are resolved by making source representation unambiguous, not by weakening the scanner.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; PostgreSQL 18 + RLS/FORCE RLS; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram, and AI/Cortex remain out of scope.
