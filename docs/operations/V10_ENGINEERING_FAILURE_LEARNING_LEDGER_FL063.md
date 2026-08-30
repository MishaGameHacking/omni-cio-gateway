# FL-063 — Provider identifiers must be protected before runner step materialization

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR PR #413; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**

Date: **2026-08-30**

WP / PR / reference: **Cloudflare integrated delivery / PR #413 / exact-head `f9cf8029878b18bf35ce90921a220a16b3ad3538`**

## Symptom / failing gate

CF-C provider workflows were fail-closed for the intended reason — the exact Neon project binding was not configured — but direct review of the Actions job log exposed a separate security defect: provider identifiers sourced from repository configuration variables were materialized in the runner step environment before the shell could execute its `add-mask` commands.

No credential value is reproduced in this entry. The affected class is private provider identity metadata, including full account/resource identifiers that project security policy forbids disclosing in CI logs.

## Root cause

The workflow attempted to retrofit secrecy inside the running shell. That ordering is invalid for data already expanded by GitHub into a step `env` mapping: runner metadata is prepared before the first shell command executes. `add-mask` is useful only after the mask has been registered; it cannot retroactively protect the step prelude.

The same review also confirmed a provider-authority coupling: a Neon project-scoped key is intentionally restricted to one project and cannot enumerate other projects. The exact project identity therefore cannot be safely rediscovered through a broader project listing without weakening least privilege.

## Blast radius searched

The correction review covered:

- both CF-C push workflows;
- Cloudflare account identity, Neon organization identity and Neon project identity inputs;
- job-wide versus step-scoped environment placement;
- the source-controlled readiness checker and candidate-delivery guard;
- exact-project Neon probe/provisioning code;
- strict tracked-content scanner behavior;
- current independent review findings and authoritative Windows gate output.

Broker secrets, production portfolio payloads, database credentials and Real execution authority were not introduced or widened.

## Corrective change

- remove repository `vars` fallback for the private provider identifier set in CF-C workflows;
- require the identifiers through step-scoped GitHub Actions `secrets` references;
- keep API credentials step-scoped as before;
- move candidate authority validation into the source-controlled readiness module;
- validate identifier shape without emitting the values;
- require the exact Neon project ID while retaining project-scoped authority and forbidding broad project discovery/create;
- add a repository guard that rejects reintroduction of `vars.*` custody for the protected provider identifier set.

## Permanent regression / guard

The candidate-delivery guard now requires secret custody for Cloudflare account, Neon organization and Neon project identities and rejects configuration-variable custody. Readiness tests cover malformed identifiers and assert that invalid values are not emitted. The strict secret scanner remains enabled without a broad allowlist.

## Future prevention rule

If a value must not appear in a GitHub Actions log, protect it before runner step materialization. Do not rely on an in-step `add-mask` command for a value already injected as ordinary workflow configuration.

For least-privilege provider credentials, supply the exact resource identity as a separate protected binding when the credential is intentionally unable to enumerate sibling resources. Do not upgrade credential scope merely to recover metadata that can be bound explicitly.
