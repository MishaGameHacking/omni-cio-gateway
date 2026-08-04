# Omni-CIO v9.0.0 — Canonical Knowledge Manifest

This file is the single source of truth for the **exact** production Knowledge upload set of the existing Omni-CIO Custom GPT after WP15 owner acceptance.

Knowledge is reference material. Behavioral, routing and execution-safety rules belong in `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt` and remain enforced server-side where applicable.

## Exact upload set — 10 files

Upload each file from `gpt/knowledge/` exactly once:

1. `02_GATEWAY_DATA_CONTRACT_V2_OPERATIONS.txt`
2. `04_CIO_PORTFOLIO_MANAGER.txt`
3. `05_ANALYST_NEWS_SIMPLE_LANGUAGE.txt`
4. `06_EVIDENCE_CREDIT_BANKRUPTCY.txt`
5. `07_PERSONAL_STRATEGY.txt`
6. `08_DECISION_JOURNAL_AND_QUALITY_CONTROL.txt`
7. `09_AUTONOMOUS_ACTION_ORCHESTRATOR.txt`
8. `10_DECISION_ENGINE_AND_CANDIDATE_COMPARISON.txt`
9. `11_RISK_DECOMPOSITION_AND_SIZING_GATES.txt`
10. `13_COMMUNICATION_STYLE_2026.txt`

No other file belongs in production GPT Knowledge for v9.0.0 unless this manifest is changed through a reviewed repository update.

## Purpose map

- `02_*` — Gateway response/data-quality interpretation and operations semantics.
- `04_*` — portfolio-manager workflow and portfolio-wide reasoning.
- `05_*` — news/public-context communication discipline.
- `06_*` — evidence, credit/default and source-quality discipline.
- `07_*` — owner strategy/policy reference concepts.
- `08_*` — decision journal, provenance and quality-control reference.
- `09_*` — tool-first orchestration and stop/error conditions.
- `10_*` — candidate funnel, `NO_ACTION`, comparison and decision discipline.
- `11_*` — risk decomposition, concentration and sizing gates.
- `13_*` — Russian communication style/output reference.

## Privacy boundary

Permanent Knowledge must contain only reusable reference material. Account-specific/private broker data and authentication material are excluded and remain in their existing external systems or authenticated request flow. Canonical secret-role documentation is `gpt/SECRETS_AND_RENDER.md`.

## Retrieval and acceptance

After replacing the Knowledge set in the **existing** GPT:

1. confirm exactly these 10 filenames are present once each;
2. remove stale/duplicate uploads;
3. in Preview ask one question that should use portfolio-manager reference and one that should use risk/decision reference;
4. verify the GPT does not treat Knowledge prose as proof that a Gateway/internal engine actually executed;
5. verify no account-specific/private material is present in Knowledge.

The repository consistency gate compares this manifest with the actual checked-in `gpt/knowledge/*.txt` set.
