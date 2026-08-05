# Omni-CIO V10 — Account Independence / Deployment Portability Amendment

Status: **OWNER-APPROVED MANDATORY V10 SCOPE / DEVELOPMENT NOT STARTED**  
Applies to: **V10 Web, API, AI, Telegram, deployment, recovery and developer workflow**  
Program state after this amendment: **0% / DEVELOPMENT NOT STARTED**

## 1. Purpose

This amendment makes explicit a V10 rule that was already implied by the GitHub Control Plane, bootstrap, release and disaster-recovery design:

> **No personal ChatGPT account, website-builder account, IDE account, hosting account, individual developer account or single physical computer may become the unique source of truth or the only place from which Omni-CIO V10 can be developed, configured, restored or deployed.**

The website and the rest of V10 must remain an ordinary repository-controlled software system that authorized developers can understand, review, modify, test and redeploy from GitHub without access to the ChatGPT account in which an earlier development conversation happened.

This is a portability and continuity requirement. It does **not** mean that broker secrets, private portfolio state or owner credentials belong in GitHub.

## 2. Canonical control model

V10 must use the following separation:

```text
PRIVATE GITHUB REPOSITORY
  = engineering source of truth / Control Plane

contains:
  code
  application configuration schemas/defaults
  architecture
  database migrations
  AI system policy / RAG policy / tool registry
  Web and Telegram source
  infrastructure/deployment definitions
  tests / CI / release manifests
  bootstrap / recovery runbooks

                |
                | reviewed release / deploy
                v

APPROVED V10 RUNTIME NODE
  = replaceable execution environment / Data Plane

contains locally:
  runtime secrets
  broker credentials
  private portfolio state
  private Decision Journal payloads
  local database
  runtime cache
  machine-specific state
```

GitHub defines **how the system works**. The runtime instance supplies **where it is currently running and the private credentials/data required by that instance**.

## 3. Mandatory invariants

### 3.1 GitHub is the engineering source of truth

The following must be repository-controlled and versioned where applicable:

- Web frontend source, assets, routes and design-system source;
- backend/API source and contracts;
- Core integration adapters;
- Telegram adapter source;
- AI provider adapters, System Policy, prompt/schema versions, RAG policy and Tool Registry;
- database schema and migrations;
- non-secret application configuration schemas and safe defaults;
- infrastructure/deployment definitions;
- bootstrap and upgrade scripts;
- CI/CD and Regression Shield definitions;
- release/build manifests and rollback instructions;
- architecture, ADRs, operations runbooks and recovery documentation.

A configuration that materially changes system behavior must not exist only in an undocumented account dashboard when it can reasonably be expressed as repository-controlled configuration/code.

### 3.2 No developer-account ownership of the product

The Web application must never depend on the identity or subscription of the developer who originally created it.

Losing access to a particular ChatGPT conversation, ChatGPT account, local IDE profile or individual developer workstation must not make V10 impossible to maintain.

A newly authorized developer/AI agent must be able to restore engineering context from the repository and continue through the normal branch/PR/test/review process.

### 3.3 No UI-builder / proprietary project lock-in

The primary V10 Web application must be source-controlled application code, not a proprietary no-code/website-builder project whose authoritative state exists only inside a vendor account.

A third-party service may host or assist the application only when the repository remains capable of rebuilding and redeploying the product elsewhere using documented interfaces.

### 3.4 Hosting is replaceable

Lenovo is the initial Personal V10 node, not the owner of the application architecture.

The same accepted V10 release must be portable, subject to documented platform prerequisites, to another approved machine/server without rewriting the Web application or financial Core.

Changing the domain, reverse proxy, approved node or hosting provider must be a deployment/configuration operation rather than a new website project.

### 3.5 Developer access is not money authority

GitHub access must never implicitly grant access to:

- `TINVEST_READ_TOKEN` values;
- `TINVEST_TRADING_TOKEN` values;
- Telegram bot token values;
- local encryption/private keys;
- private broker payloads;
- full account identifiers;
- private portfolio/Decision Journal database contents;
- transfer/withdrawal authority.

Repository collaborators can receive the GitHub role required for their engineering work while runtime secrets remain isolated by the V10 secret/privilege boundary.

**Full ability to develop the site does not mean full ability to trade the owner's money.**

### 3.6 Runtime-only values use explicit schemas

Machine/account-specific values may live outside GitHub, but their **names, schemas, validation rules, safe examples and provisioning procedure** must be versioned in GitHub.

Example:

```text
GitHub:
  TINVEST_READ_TOKEN = required secret reference / validation contract

Runtime secret store:
  actual secret value
```

No undocumented dashboard toggle or local manual edit may become a hidden required dependency of normal V10 operation.

### 3.7 Reproducible development environment

V10 must provide documented/bootstrap-assisted steps so an authorized developer can obtain the repository and reproduce a supported development/test environment without copying an opaque working directory from the original developer's machine.

At minimum the repository must define:

- supported Python/Node/toolchain versions;
- dependency locks;
- local non-secret configuration examples;
- database migration/bootstrap procedure;
- frontend/backend start and test commands;
- CI parity expectations;
- required external services and how they are mocked/disabled for development.

### 3.8 Reproducible deployment

An approved release must be deployable from a reviewed Git commit/release artifact rather than from an untracked developer working tree.

The runtime must expose enough non-secret build metadata to identify the installed release, including V10 version and Git SHA.

### 3.9 Clean-room portability acceptance

Before V10 can be called `100% COMPLETE`, the project must pass a portability/recovery rehearsal in which a fresh approved environment is brought up using:

1. GitHub source/release;
2. documented bootstrap/deployment procedure;
3. versioned migrations/configuration contracts;
4. an authorized backup where private durable state is required;
5. separately restored runtime secrets.

The procedure must not depend on the original ChatGPT account, the original developer session, undocumented website-builder state or manual recollection of hidden settings.

### 3.10 Account-independent AI

The own V10 AI Copilot/Agent Orchestrator must use repository-controlled System Policy, Knowledge/RAG configuration and Tool Registry plus private runtime state. Its mandatory intelligence must not exist only inside the current Custom GPT account.

The existing Custom GPT remains a migration/reference/fallback asset until the explicit parity gate, but its eventual removal from the required runtime path must not delete the source knowledge/configuration migrated into V10.

## 4. Work-package integration

This amendment does not create a parallel roadmap. It modifies the acceptance criteria of existing V10 work packages:

### WP0 — Program Lock / Architecture Freeze

Add `Account Independence / Deployment Portability` to the mandatory V10 architecture/security invariants.

### WP1 — Repository Architecture

Define repository ownership of Web/API/AI/Telegram/infrastructure/configuration artifacts and forbid account-only authoritative project state.

### WP3 — Regression Shield

Add repository/portability guards where practical, including checks that required application configuration contracts and generated build metadata are versioned.

### WP4 — Release / Deployment Contract

Require deployment from reviewed Git evidence and expose installed version/Git SHA. Hosting/provider-specific state must be minimized and documented.

### WP6 — Privilege Separation

Ensure developer/runner access is separated from runtime trading-secret authority.

### WP7 — One-Time Bootstrap

Bootstrap must support a fresh approved node and must not depend on the original developer account/workstation.

### WP8 — Secret Store

Keep actual secrets outside GitHub while keeping their configuration contracts/provisioning documentation inside the repository.

### WP16–WP22 — Web Platform

The primary site must be normal source-controlled Web application code. No proprietary website-builder account may become the authoritative source of the product.

The Web System/Admin page should expose the non-secret deployed V10 version/Git SHA and relevant runtime health so the owner can identify which reviewed release is running.

### WP30A / WP30B / WP32A–WP33A — AI migration and Copilot

Move the required GPT knowledge/policies/tool contracts into repository-controlled V10 assets and private runtime state so AI continuity does not depend on the current ChatGPT account.

### WP45 — Full System Integration

End-to-end deployment evidence must start from a reviewed GitHub release, not an untracked developer state.

### WP49 — Disaster Recovery Rehearsal

The recovery rehearsal is also the formal **Account Independence / Deployment Portability acceptance test**.

### WP50 — Final Release

V10 cannot reach `100% COMPLETE` until the portability acceptance test is green and the owner can replace the development account/runtime machine without losing the application architecture or engineering source of truth.

## 5. Developer collaboration model

Multiple developers should collaborate primarily through GitHub permissions and repository workflows, not by sharing one personal website-admin account.

Default engineering flow remains:

`GitHub access -> branch -> code/config change -> tests -> PR -> review -> exact-head gates -> accepted merge -> reviewed deployment`

Production/runtime authority is a separate security decision.

Where GitHub repository/organization roles, branch protection, runner groups or deployment controls are available and suitable for the owner's plan, V10 should use them to reduce shared-account practices and constrain who can modify/deploy code.

## 6. Forbidden architecture patterns

The following patterns violate this amendment unless a later owner-approved amendment explicitly replaces the rule:

- site source exists only inside a ChatGPT/website-builder/hosting account;
- the only editable copy is on one Lenovo filesystem;
- developer must know an undocumented password or hidden dashboard toggle to rebuild the system;
- frontend changes are made directly on production and are not represented in Git history;
- production runs code that cannot be mapped to a reviewed commit/release;
- one developer account is the only holder of required non-secret application configuration;
- granting GitHub Write automatically reveals the owner's trading secret;
- migrating to another approved runtime requires recreating the website from scratch;
- Custom GPT is removed before its required knowledge/policies/tools have a V10-controlled replacement.

## 7. Completion evidence

The amendment is complete only when repository/runtime evidence proves all of the following:

- a supported development environment can be reproduced from repository documentation and locks;
- the Web application can be built from GitHub without the original ChatGPT/developer account;
- an accepted release can be deployed to a fresh approved node;
- private durable state can be restored from the documented backup path;
- runtime secrets can be reprovisioned separately without entering Git history;
- the deployed instance reports the expected release/Git SHA;
- a developer with repository access can modify/test the Web project without receiving broker trading credentials;
- no account-only hidden configuration is required for normal V10 operation;
- AI mandatory knowledge/policy/tool configuration is controlled by V10 rather than being trapped only inside Custom GPT;
- final disaster-recovery/portability rehearsal is green.

## 8. External planning references

Official GitHub references to re-check immediately before implementation:

- Self-hosted runners: `https://docs.github.com/en/actions/reference/runners/self-hosted-runners`
- Managing access to self-hosted runner groups: `https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/manage-access`
- Deployments and environments: `https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments`

These references are planning guidance. Exact GitHub plan-dependent controls must be verified at the implementation date and must not be assumed available merely because they are described by GitHub.

## 9. Program-state rule

Recording this amendment is documentation/governance work only.

It **does not start V10 implementation**, does not deploy a site, does not alter V9 runtime authority and does not grant any new broker permission.

Current V10 state remains:

`PROGRAM LOCKED / DEVELOPMENT NOT STARTED / 0%`


## 10. Consolidation status

This amendment's mandatory requirements have been incorporated into the canonical `OMNI_CIO_V10_MASTER_PLAN.md` and regenerated paired PDF during the final plan-readiness pass. This file is retained as historical owner-approved audit evidence. It is no longer a competing source of truth; if wording differs, the accepted canonical Master Plan + Program Lock govern future implementation.
