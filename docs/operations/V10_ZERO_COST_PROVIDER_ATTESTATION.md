# Omni-CIO V10 zero-charge provider attestation

Status: **REQUIRED BEFORE EVERY PHASE 4 PROVIDER APPLY**

## Purpose

The Phase 4 public preview is authorized only at zero recurring cost. Neon exposes
its organization plan through the API, so the deployment workflow verifies that
the connected Neon organization is exactly on the `free` plan.

Render exposes the service plan through the API but does not expose whether the
workspace has a payment method attached. A Render Free service can still create a
charge when billable overage is allowed by an attached payment method. Therefore
the accepted-main workflow requires a fresh OWNER attestation before any provider
mutation.

A missing, malformed, stale or future-dated attestation stops the workflow RED.
It must never be bypassed with a default value.

## Non-delegable OWNER check

Immediately before the accepted-main deployment:

1. Open the Render workspace billing/settings page.
2. Confirm the target workspace has no card or other payment method attached.
3. Confirm the workspace and target service have not been upgraded to a paid plan.
4. Record the current UTC timestamp to whole seconds.
5. In the GitHub repository, open **Settings -> Secrets and variables -> Actions -> Variables**.
6. Create or update the repository variable named:

   `RENDER_ZERO_CHARGE_ATTESTATION`

7. Set its value to this exact form:

   `NO_PAYMENT_METHOD_CONFIRMED:YYYY-MM-DDTHH:MM:SSZ`

Example:

`NO_PAYMENT_METHOD_CONFIRMED:2026-08-21T09:00:00Z`

This value is not a provider secret. It is a time-bounded OWNER statement. The
workflow accepts it for at most 24 hours and allows at most five minutes of future
clock skew.

## Automated proof

Before either provider can be mutated, the workflow runs:

`python scripts/check_v10_zero_cost_provider_boundary.py`

The preflight:

- validates the exact Render attestation format and freshness;
- uses `NEON_API_KEY` only for a read-only call to
  `GET /api/v2/users/me/organizations`;
- requires exactly one reachable Neon organization;
- requires its plan to equal `free`;
- emits only sanitized PASS classifications;
- returns non-zero on invalid credentials, ambiguous organization scope, paid
  Neon plan, network uncertainty or invalid Render attestation.

The Render and Neon resource provisioner runs only after this preflight succeeds.

## Stop conditions

Do not deploy when any of these conditions is true:

- Render shows a card or payment method;
- Render shows a paid workspace or service plan;
- the OWNER cannot verify the billing state directly in the Render UI;
- the attestation is older than 24 hours;
- the Neon API key reaches zero or multiple organizations;
- the Neon organization plan is not exactly `free`;
- either provider requests payment, card verification, paid overage or broader
  authority.

No payment method may be added merely to keep the preview online. Free-tier
suspension is an accepted fail-closed outcome; a surprise charge is not.
