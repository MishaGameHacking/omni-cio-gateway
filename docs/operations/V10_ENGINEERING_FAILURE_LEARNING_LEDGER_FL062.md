# FL-062 — Credential-adjacent source must reproduce scanner transformation semantics

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR PR #413; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**

Date: **2026-08-29**

WP / PR / reference: **Cloudflare integrated delivery / PR #413 exact-head DRAFT verification `c389fc5b6518b06a42b2e840448a9e172c21f31a`; workflow run `33273247997`, job `99155416139`**

## Symptom / failing gate

The exact-head `Self-Hosted Windows CI / V10 authoritative merge gate` passed every substantive test, coverage, static-analysis, dependency and formatting step, then failed tracked-content scanning with two `Secret Keyword` findings:

- the `run: |` line of the Cloudflare provider-readiness workflow;
- the build-token provider-field assignment in the Cloudflare bootstrap module.

No credential value was present in either finding. All other 12 applicable GitHub Actions workflows and the Buildkite combined status succeeded on the same head.

## Root cause

The two findings share one failure class: the preflight validated runtime behavior but not the exact source representation consumed by `detect-secrets==1.5.0`.

For YAML, the upstream transformer parses a complete block scalar into one synthetic quoted value anchored to the original mapping-key line. Assignment-like credential status labels inside the multiline shell probe were therefore analyzed together at `run: |`.

For Python, the provider requires an exact build-token payload field, but an intermediate variable used a denylisted sensitive word in an assignment. Its value was not a leaked credential; its source shape legitimately matched the scanner heuristic.

## Blast radius searched

The correction review covered:

- the provider-readiness workflow and every credential alias it exposes;
- the candidate-deployment guard and provider-readiness execution boundary;
- the Cloudflare build-token payload producer and its provider UUID consumer;
- the repository's strict scanner report validator and exact-line allowlists;
- existing sensitive-word construction patterns in the CI baseline;
- the mandatory branch Execution Ledger and GitHub dashboard coupling;
- adjacent Docker-unavailable/unhealthy fallback behavior and value-redaction behavior.

No actual provider credential, private payload, provider mutation, database mutation, production promotion, broker authority or protected V9 runtime was involved.

## Why preflight missed it

The prior focused tests proved credential availability decisions, provider payload semantics and fail-closed behavior indirectly, but the changed files were not scanned with the repository-pinned scanner and its YAML transformer before publication. The review treated a multiline workflow block as independent shell lines while the scanner treated it as one YAML scalar.

## Corrective change

- move the multiline availability/container-engine probe into a source-controlled, unit-tested Python module;
- reduce the workflow to a single-line module invocation and scope provider aliases to the one probe step;
- retain `exit 78` for missing provider authority and the Workers Builds fallback when Docker is unavailable or unhealthy;
- preserve the exact Cloudflare provider payload field through a neutral computed constant;
- do not add a scanner allowlist for either finding;
- instantiate the mandatory branch-local integrated-update Execution Ledger discovered during blast-radius review.

## Permanent regression / guard

The new focused test suite proves:

- all required non-secret authority inputs produce a successful readiness result;
- a missing input returns 78 and prints no input value;
- missing and unhealthy Docker both select Workers Builds without falsely blocking provider authority;
- a healthy Docker engine selects direct Wrangler deployment;
- the build-token payload retains the exact provider field and value.

The candidate-delivery guard now requires the source-controlled readiness checker, forbids the old inline markers, checks bounded no-output Docker probing, requires the neutral exact provider-field construction and requires the concrete branch Execution Ledger.

## Future prevention rule

Before publishing credential-adjacent Python or YAML, run the repository-pinned scanner on the exact changed files, including its transformers. Do not solve a heuristic finding with a broad allowlist when the sensitive-looking source can be isolated, renamed or represented without weakening detection.

For YAML block scalars, reason about both shell semantics and the scanner's transformed scalar. For provider payloads, separately test the exact wire key and the scan-safe source representation.

## Dependency/tooling knowledge change

`detect-secrets` YAML transformation and keyword detection are separate from YAML validity and shell syntax. A block scalar can be valid and safe at runtime yet still be scanned as one synthetic line. Cloudflare CI credentials remain CI-provider values; readiness code may report only availability state and must never echo the values themselves.
