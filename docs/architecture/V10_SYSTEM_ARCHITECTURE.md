# Omni-CIO V10 — System Architecture

Status: **WP0 architecture freeze / design authority**  
Runtime effect: **none until later work-package Exit Gates**  
Protected runtime baseline: **Omni-CIO v9.0.0**

## 1. Purpose

This document defines the target architecture of Omni-CIO V10 before implementation begins. It prevents Web, Telegram, AI, Lenovo infrastructure and broker execution from being developed as competing systems.

V10 is one platform with one deterministic financial Core and several adapters. Existing V9 remains the production/recovery baseline until an explicit later V10 work package replaces a boundary and passes its acceptance gate.

## 2. Architectural principles

1. **One repository / one platform / one Core.**
2. **GitHub is the engineering Control Plane**, not a secret store or broker account.
3. **Runtime nodes are replaceable Data Plane instances.** Lenovo is first, not unique.
4. **Interfaces are adapters.** Web, Telegram and Custom GPT do not own financial business logic.
5. **AI is an analytical/orchestration layer**, never direct broker-write authority.
6. **Money-critical calculations and authority gates are deterministic.**
7. **Secrets/private portfolio state remain outside GitHub.**
8. **Every replacement is staged and reversible.** V9 is protected until V10 final acceptance.
9. **Degraded operation is explicit.** AI/Telegram may be unavailable without silently changing financial authority.
10. **Public/multi-user is outside V10 Personal.** Data models may be tenant-ready, but only OWNER is enabled.

## 3. Target logical architecture

```text
                         PRIVATE GITHUB
                engineering Control Plane
       code / policies / tests / CI / releases / runbooks
                              |
                     reviewed release only
                              v
                    APPROVED V10 NODE
                       (Lenovo first)
                              |
     +------------------------+-------------------------+
     |                        |                         |
     v                        v                         v
Omni-CIO Core           Durable State          Research / AI Layer
     |                  PostgreSQL/local              |
     |                        |                  Collector / RAG
     |                        |                  AI Copilot/Agent
     |                        |                  Autonomous Research
     |                        |                         |
     +------------------------+-------------------------+
                              |
                         Internal API
                    +---------+---------+
                    |                   |
                    v                   v
                 Web App           Telegram Adapter
                    |                   |
                    +---------+---------+
                              |
                              v
                         OWNER interface

External data/authority boundaries:

T-Invest READ  ---> Portfolio/Market adapters ---> Core
T-Invest REAL  <--- isolated Execution service <--- approved immutable plan only
Official sources ---> Research Collector ---> Evidence Engine ---> Core/AI
Current Custom GPT ---> retained migration/fallback interface until parity gate
```

## 4. Component responsibilities

### 4.1 GitHub Control Plane

Owns:

- source code;
- architecture and ADRs;
- configuration schemas and safe defaults;
- DB migrations;
- AI system policies/tool contracts/evals;
- CI/security policy;
- bootstrap/deployment/recovery automation;
- release identity and rollback documentation.

Must not own:

- real broker tokens;
- Telegram bot token;
- encryption/private keys;
- full account identifiers;
- private portfolio/operations payloads;
- runtime-only private Decision Journal payloads.

### 4.2 Lenovo Personal Node

First approved V10 runtime. Planned responsibilities after Block C acceptance:

- Core API/runtime;
- local durable database;
- Watchtower scheduler/jobs;
- Web application;
- Telegram adapter;
- local AI provider/worker when enabled;
- observability/backup/recovery agents.

The node must be reproducible from GitHub + documented bootstrap + authorized backup + separately restored secrets.

### 4.3 Omni-CIO Core

Single source of deterministic financial logic. V10 reuses/isolates reviewed V9 engines rather than rewriting them without proof:

- Portfolio / policy / universe;
- Research contracts / Credit / Fund X-Ray;
- Portfolio Risk;
- Strategy;
- Optimizer;
- immutable Plans;
- plan execution lifecycle;
- Watchtower;
- Decision Journal/evaluation.

The Core does not depend on a specific UI or LLM provider.

### 4.4 Web App

Primary owner cabinet after Block E acceptance. It renders canonical Core DTOs and does not reimplement financial calculations in browser-only logic.

Planned areas: Overview, Portfolio, Assets, Watchtower, Research, Risk, Decisions, Plans, Execution, Journal, System/Admin, Settings, AI Copilot.

### 4.5 Telegram Adapter

Alert/entry surface, not a second financial brain.

Responsibilities:

- OWNER identity/auth handoff;
- material alerts;
- simple status/summary commands;
- deep link/Mini App navigation into the same Web application.

No broker secret and no independent sizing/execution logic lives in Telegram.

### 4.6 AI Copilot / Agent Orchestrator

Replaceable AI layer shared by Web and Telegram.

Allowed role:

- conversational interface;
- retrieval over versioned Knowledge/RAG;
- structured research synthesis;
- source/evidence comparison;
- allowlisted analytical tool orchestration;
- explanation of deterministic Core results.

Forbidden role:

- direct `PostOrder`/broker-write calls;
- bypass of Risk/Optimizer/Plan approval;
- treating ungrounded model output as evidence;
- silent expansion of permissions.

### 4.7 Research and Evidence

Research Collector retrieves only approved sources. Evidence Engine normalizes provenance, identity, timestamps, freshness and contradictions before strong conclusions.

AI may help classify/summarize evidence, but model output does not become canonical evidence without source binding.

### 4.8 Execution service

Separate narrow authority boundary. It receives only a validated immutable plan and explicit owner approval through the reviewed lifecycle.

It preserves V9 invariants unless a later V10 package explicitly replaces them:

- separate trading credential;
- own-funds BUY / own-position SELL;
- no transfer/withdraw/margin/short;
- fresh preflight;
- price-step/limits;
- one idempotent possible submit;
- ambiguous submit -> reconciliation only;
- submitted != filled without broker proof.

## 5. Deployment stages

V10 is intentionally staged:

1. **WP0** — architecture/program freeze only.
2. **WP1–WP4** — repository/toolchain/CI/release contract.
3. **WP5–WP10** — one-time Lenovo infrastructure and recovery foundation.
4. **WP11–WP15** — independent Core/data/job/broker-read layer.
5. **WP16–WP22A** — Web application and external-access security gate.
6. **WP23–WP26** — Telegram adapter/integration.
7. **WP27–WP33** — Research/AI/GPT migration/evals.
8. **WP34–WP38** — Guardian/Watchtower decision loop.
9. **WP39–WP44** — Shadow then Personal Real Execution.
10. **WP45–WP50** — full integration, hardening, recovery and V10 release.

No stage is permission to skip the prior Exit Gate.

## 6. Runtime compatibility rule

Until the relevant V10 package explicitly replaces it:

- production remains current V9 on Render;
- endpoint remains `https://omni-cio-gateway.onrender.com`;
- entrypoint remains `app:app`;
- current GPT v9.0.0 remains applied;
- V9 execution/Watchtower kill switches remain authoritative.

New V10 components must first coexist with or run separately from the accepted V9 runtime without silent production takeover.

## 7. Account independence

No personal ChatGPT account, website builder, developer laptop or hosting dashboard may become the only copy of authoritative application state.

A new authorized developer must be able to restore engineering context from GitHub. A new approved runtime must be able to restore operation from reviewed release + bootstrap + backup + separately restored secrets.

## 8. Architecture freeze rule

Changes to this target architecture require an ADR and, if scope/authority changes materially, an owner-approved V10 program amendment.

A brainstorm/chat idea is not an architectural change until accepted through that process.
