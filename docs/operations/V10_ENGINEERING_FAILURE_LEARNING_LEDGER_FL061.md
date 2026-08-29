# FL-061 — Governance publication must reproduce formatter, shell syntax, and fail-closed contract coverage

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR PR #410; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-29**  
WP / PR / reference: **Amendment 15 integrated Cloudflare delivery governance / PR #410 exact-head DRAFT verification `976dbc32e6506e9f09251ae3a51a18c518c6ec47`**

## Symptom / failing gate

The first published Amendment-15 DRAFT head produced two applicable GitHub Actions RED results even though the new governance contract and its focused semantic tests passed:

1. `Self-Hosted Windows CI / V10 authoritative merge gate` failed because `python -m ruff format --check` reported that the new integrated Cloudflare guard was not in canonical repository format.
2. `V10 Engineering Governance` executed every substantive governance/compile/test step successfully, then failed in `Clean self-hosted workspace` because the newly edited Bash cleanup block omitted its closing `fi`.

Independent Files-changed review also found a safety-relevant fail-open gap: the machine contract declared `product_activation` gates, but the new guard did not validate that section, so those values could have been weakened without making the governance check fail.

SonarCloud, Semgrep and the Gitar check surface had zero annotations/new issues on the same head, proving again that a green aggregate check does not replace exact changed-files review.

## Root cause

The pre-publication fixture review tested Python syntax, JSON semantics and the new contract's primary authority matrix, but it did not reproduce three exact repository/tooling contracts:

- canonical Ruff formatting for the changed Python guard;
- Bash parser closure for the changed workflow shell block;
- one-to-one validation coverage for every safety-relevant machine-contract section.

The failure class is therefore a **preflight fidelity gap**, not three unrelated defects. The branch was published before the local/focused validation model matched the exact formatter, shell-language and fail-closed contract completeness enforced by the repository and independent review.

## Blast radius searched

The correction review covered:

- `scripts/check_v10_cloudflare_public_product_integrated.py`;
- `tests/test_v10_cloudflare_public_product_integrated.py`;
- `.github/workflows/v10-engineering-governance.yml`;
- the Amendment-15 machine contract, especially `product_activation`;
- the Amendment-15 lifecycle/status markers;
- the adjacent Amendment-14 platform-authority diagnostic that still described the former first stage as the current "Next stage";
- existing governance workflow cleanup patterns and self-hosted exact-head bootstrap/cleanup law;
- Sonar/Gitar/Semgrep outputs and the unresolved inline review thread;
- existing dependency/broker deprecation warnings, which were classified as pre-existing CF-B compatibility debt and not mixed into the focused governance repair.

No product Web/runtime, Cloudflare provider resource, PostgreSQL data, tenant session, broker authority or protected V9 runtime is mutated by this correction.

## Why preflight missed it

The initial preflight used a reduced semantic fixture rather than the exact repository formatter and modified workflow shell parser. It also reviewed the new contract by expected high-level sections but did not enforce a structural invariant that every safety-relevant section must have a corresponding validator.

This was insufficient for a change that modified both Python governance code and GitHub Actions shell source. The prior PR #408 lesson about reviewing non-GREEN annotations was applied, but the local preflight itself still lacked exact-tool fidelity for all changed languages.

## Corrective change

- format the new guard to canonical Ruff formatting before the next published head;
- add `_validate_product_activation` and require the public multi-user, Telegram/VK and T-Invest activation gates to remain fail-closed;
- include that validator in the flat-orchestrator AST regression contract;
- require exact Amendment-15 lifecycle/progress markers in the guard;
- close the governance cleanup Bash conditional with `fi`;
- add a deterministic regression assertion for the complete cleanup block;
- update the adjacent Amendment-14 diagnostic so it no longer presents the old standalone build-integration stage as current-next authority after Amendment 15;
- retain all existing Cloudflare provider, WEB VISUAL, V9 and Real-money locks.

## Permanent regression / guard

The Amendment-15 regression suite now verifies:

- exact CF-A -> CF-D authority tuples;
- the `product_activation` fail-closed values;
- WEB VISUAL and broker/Real-money locks;
- the thin `_validate_contract` call graph including `_validate_product_activation`;
- the governance workflow cleanup block including its closing `fi`;
- execution of the repository Amendment-15 guard itself.

The Amendment-15 guard also checks the governance workflow's cleanup markers and exact amendment lifecycle markers. Future publication readiness must include the repository's exact Ruff formatter check for changed Python governance sources and shell-syntax validation for changed workflow shell blocks rather than a reduced substitute.

## Future prevention rule

Before publishing a governance/CI head, classify every changed file by executable language/tooling and run the same cheap deterministic parser/formatter used by the authoritative gate wherever practical. For machine contracts, require validator coverage for every safety/authority-bearing section, not only the sections expected to change.

A successful semantic fixture is not sufficient publication evidence when the repository's exact formatter, workflow shell syntax or fail-closed section coverage has not been reproduced.

## Dependency/tooling knowledge change

Ruff formatting is an independent required contract from Ruff linting: `ruff check` success does not imply `ruff format --check` success. GitHub Actions accepts multiline Bash source as YAML text without proving the shell block is syntactically closed; the shell parser remains an independent validation boundary. Independent review can find authority gaps even when aggregate code-quality checks report success and zero annotations.
