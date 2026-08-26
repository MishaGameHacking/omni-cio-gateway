# FL-039 — Heterogeneous provider collections must be typed to their common protocol

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 5; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-25**  
WP / PR / reference: **WP22A Phase 5 integrated technical closeout / PR #391 / DRAFT head `e45ada5d`**

## Symptom / failing gate

The exact-head DRAFT cycle for PR #391 reached multiple independent V10 Web audit workflows. Their frontend dependency reproduction, TypeScript typecheck, lint, unit tests, production build, Playwright browser evidence and npm audit completed successfully. The Python static stage then ran the repository-wide `python -m mypy` and failed on the same provider-composition line in every workflow that reached that stage.

The reported error was that appending `VkIdOauthRuntimeV1` to `runtimes` was incompatible with the list type inferred from the earlier `TelegramOidcRuntimeV1` append.

The repeated failures were one shared source defect, not independent WP15/WP18/WP20/WP22 or runner defects. Under V10 policy the head remained RED and no partial success was used as merge evidence.

## Root cause

`build_wp22a_phase5_provider_auth()` created the provider runtime collection with an unannotated empty list:

`runtimes = []`

The first conditional append added a `TelegramOidcRuntimeV1`. Mypy therefore inferred a list specialized to that concrete runtime. The later VK branch appended `VkIdOauthRuntimeV1`, which correctly implements the same provider-auth runtime protocol but is not the Telegram concrete class.

The implementation intended a heterogeneous collection of provider adapters behind `ProviderAuthenticationRuntimeLike`, while the static declaration accidentally described a homogeneous Telegram-only collection.

## Blast radius searched

The review covered:

- the complete `build_wp22a_phase5_provider_auth()` composition path;
- Telegram and VK runtime construction;
- `ProviderAuthenticationRuntimeLike`, the shared protocol consumed by `ProviderAuthRouteServicesV1`;
- all current exact-head workflows whose static stage runs repository-wide mypy;
- the provider route consumer, which accepts a tuple of the common runtime protocol rather than a Telegram-specific tuple;
- runtime behavior and provider authority boundaries, confirming the defect was static composition typing only and did not create a login bypass, tenant-scope change, secret exposure or provider fallback.

No analogous concrete-type narrowing was required in the provider route service because its public contract is already expressed in terms of `ProviderAuthenticationRuntimeLike`.

## Why preflight missed it

The branch had source, security, recovery and full-diff review, but the current execution environment could not run the repository's private exact `mypy` graph locally. The PR description explicitly did not claim local mypy PASS and used the DRAFT cycle as the first executable repository-wide verifier.

The source review also concentrated on runtime/provider/security semantics and did not explicitly challenge type inference for the heterogeneous adapter collection before that cycle.

## Corrective change

Import the existing common provider runtime protocol and declare the collection explicitly:

`runtimes: list[ProviderAuthenticationRuntimeLike] = []`

Telegram and VK adapters are then checked structurally against the same accepted consumer contract. No `Any`, `cast`, `# type: ignore`, mypy exclusion, workflow narrowing or dependency change is introduced.

The correction is type-contract only; provider selection, runtime behavior, session issuance and fail-closed configuration semantics remain unchanged.

## Permanent regression / guard

The explicit common-protocol annotation is the local permanent guard: any future runtime appended to this collection must satisfy `ProviderAuthenticationRuntimeLike` under static analysis.

Repository-wide `python -m mypy` remains unchanged and is executed by the applicable V10 gates. Because the consumer also declares the common protocol, static producer/consumer drift will continue to fail closed without weakening CI.

## Future prevention rule

When an empty Python collection is intended to hold multiple implementations of one interface or protocol:

1. annotate the collection with that common interface/protocol at construction time;
2. do not rely on the first `append` to infer the long-term collection type;
3. review the downstream consumer's declared contract and type the producer to that contract;
4. do not solve heterogeneous-adapter errors with `Any`, casts, ignores or CI exclusions;
5. include exact repository mypy, or a provably equivalent focused invocation, in pre-CI whenever new typed runtime composition is introduced.

A repeated identical static error across several workflows should be treated as one shared source defect until evidence proves otherwise.

## Dependency/tooling knowledge change

No dependency update is required. The accepted mypy toolchain remains unchanged. Current mypy documentation confirms that empty collection types can be inferred from modification operations such as `append`, while explicit collection annotations are the correct way to provide the intended type context for more complex or heterogeneous cases.
