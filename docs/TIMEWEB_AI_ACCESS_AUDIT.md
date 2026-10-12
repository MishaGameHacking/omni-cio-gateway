# Timeweb AI access audit

Date: 2026-10-12

## Verified access

- The existing `TIMEWEB_CLOUD_TOKEN` connects successfully to the official Timeweb Cloud MCP endpoint.
- MCP initialization succeeded with protocol version `2025-06-18`.
- The endpoint returned 226 available infrastructure tools.
- The token already works for the deployed Analyst AI cloud server and backend deployment workflow.

## AI access checks

- A direct request to `https://api.timeweb.ai/v1/models` with `TIMEWEB_CLOUD_TOKEN` returned HTTP 401.
- This confirms that the Timeweb Cloud infrastructure token is not an AI Gateway API key.
- The MCP catalog exposes AI Agent operations such as `list_ai_agents`, `list_ai_models`, and `create_ai_agent`.
- Calling `list_ai_agents` returned `forbidden`: the current token does not have the IAM permission required for AI resources.
- The available MCP key-management tools cover SSH and S3 keys only. They do not expose creation or recovery of AI Gateway API keys or AI Agent API access keys.

## Consequence for Analyst AI

- The backend has the Timeweb AI client and rules-first orchestration code, but live paid model calls cannot start with the credentials currently available to automation.
- The deployment workflow expects `TIMEWEB_AI_TOKEN`, `TIMEWEB_AI_BASE_URL`, `AI_MODEL_FAST`, `AI_MODEL_STANDARD`, and `AI_MODEL_PREMIUM`.
- The last production deployment received empty values for those AI settings, so the system remains fail-closed and spends no AI tokens.

## Required account-side access

To finish the live connection, the credential stored as `TIMEWEB_CLOUD_TOKEN` must have AI IAM access, and a separate AI Gateway API key must be issued in the Timeweb control panel and stored as the GitHub secret `TIMEWEB_AI_TOKEN`. The AI Gateway key is shown only once by the control panel and cannot be recovered later.
