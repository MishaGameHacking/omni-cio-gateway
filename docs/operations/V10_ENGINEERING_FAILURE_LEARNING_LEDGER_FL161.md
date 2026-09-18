# V10 Engineering Failure Learning — FL161

Failure class: `CF_D_HOSTED_CUSTODY_TOKEN_AFTER_EXACT_BUILD`

Date: 2026-09-18

Scope: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D / hosted production custody resync`

## Observed failure

Production Release #75 on exact accepted main `bf4f92438f1eff6440e1c308a86950b4a9a25108` proved the FL160 dependency repair: the hosted lock installed and verified all seven canonical hash-locked packages successfully.

The required hosted production database recovery then stopped before Neon database mutation with:

`CLOUDFLARE_NEON_HOSTED_BOOTSTRAP=STOPPED code=CLOUDFLARE_CF_D_ORIGIN_SYNC_UNAUTHORIZED status=403`

The sanitized Neon diagnostic still reported `EXACT_PROJECT_BRANCH_READABLE`. Production promotion was skipped and the terminal release DAG failed closed.

## Root cause

The hosted production custody bridge had reintroduced the exact lifecycle ordering that FL099 already prohibited.

The accepted candidate lifecycle is version-bound:

`arm sync token -> exact manual Build -> Build terminal success -> one 100% active version -> exact-SHA release proof -> custody request -> token cleanup`

The hosted recovery instead executed:

`exact-SHA release proof -> arm sync token -> custody request`

A staging Worker secret mutation is version/deployment-coupled. Arming the token after the exact release proof can create/deploy a new Worker version and invalidates the assumption that the just-attested serving version and the fresh token are one authoritative state. The observed 403 is therefore a deterministic authorization/configuration failure, not a retryable transport condition.

## Blast radius

- the normal gated candidate path already obeys FL099 and remains correct;
- hosted staging recovery does not use production branch custody;
- only hosted production missing-secret recovery used the post-attestation token mutation sequence;
- the production branch identifier remains private to the bounded custody handoff;
- Neon authority remains project-scoped and exact-branch;
- no product-auth, public-user, broker-write or Real-money authority changes.

## Permanent correction

Do not add a 403 retry and do not create a second custody protocol.

The hosted production adapter now reuses `run_v10_cloudflare_gated_candidate.run(..., source_branch="main")`. That accepted lifecycle:

- arms the ephemeral token before a fresh exact-main staging Build;
- waits for Build terminal success;
- proves one 100% active staging version;
- proves the exact source SHA through the source-controlled release endpoint;
- performs custody with no intervening secret mutation;
- cleans the token;
- writes the bounded main-only `RUNNER_TEMP` handoff;
- preserves persistent-origin cleanup and quarantines the temporary trigger.

Only after that shared version-bound lifecycle returns may the unchanged canonical production provisioner read the handoff and perform exact project/branch/default/ready checks before PostgreSQL mutation.

## Permanent regression guards

Deterministic tests require:

- the hosted production adapter delegates custody reacquisition to the accepted gated lifecycle with `source_branch="main"`;
- the hosted adapter contains no direct token arm, custody fetch, pre-custody release proof or handoff-write reimplementation;
- custody remains before canonical production runtime provisioning and runtime-secret write;
- no branch collection enumeration is introduced;
- the architecture records `HOSTED_CUSTODY_REUSES_VERSION_BOUND_CANDIDATE`;
- 403 remains non-retryable and fail-closed under the existing custody tests;
- the existing candidate lifecycle ordering tests continue to freeze token-before-Build semantics.

## Acceptance requirement

The correction is not accepted by source change alone. The exact PR head must pass DRAFT and READY verification, Sonar and zero blocking review threads, squash-merge, exact-new-main post-merge acceptance, and a fresh V10 Cloudflare Production Release.

That release must prove hosted production recovery `success`, production promotion `success`, and terminal release DAG `success`. Any newly exposed failure is a separate bounded `MAIN_RED_STOP` defect and must not be hidden by retrying 403.
