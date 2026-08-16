# ADR-0012 — WP22A Clientless OWNER Access via Cloudflare Access + Tunnel

Status: **PROPOSED / WP22A IMPLEMENTATION IN PROGRESS**

Date: 2026-08-16

## Context

The accepted browser-only/headless V10 amendment requires the OWNER's normal phone path to work in a standards-compliant browser without a VPN/device client. WP22A must expose the existing Personal Web App without turning the Lenovo into an Internet-facing origin, weakening server-side sessions, creating a second Web App, or activating public multi-user access.

The earlier Tailscale Serve implementation does not satisfy the updated OWNER phone requirement because ordinary tailnet access from a phone depends on the Tailscale device client.

## Decision

Adopt **Cloudflare Access + a named Cloudflare Tunnel** as the WP22A implementation candidate, subject to the full WP22A Exit Gate.

The intended path is:

`phone browser -> Cloudflare Access -> named Tunnel -> cloudflared -> 127.0.0.1:8765 -> existing Omni-CIO Web`.

The Tunnel ingress must validate the Access JWT before proxying by configuring `access.required=true`, exact `teamName` and the exact Access application audience tag. The local Web boundary independently requires a Cloudflare Access assertion, exact external Host, loopback proxy peer, Origin/CSRF controls, rate limits, security headers and the existing PostgreSQL-backed session registry.

Cloudflare Access is an outer OWNER-private reachability gate. It does not replace the accepted Telegram/VK product identity model and does not authorize public registration. The private Personal V10 route creates only the existing OWNER tenant session after the Access boundary has been satisfied.

## Why this candidate

Cloudflare meets the current V10 requirements better than the prior phone Tailscale path because it provides browser-only clientless access, an outbound-only connector, Access authentication, API/Terraform automation and no need to expose Lenovo's origin port publicly.

The initial target is the Zero Trust Free tier only if final documented limits continue to satisfy Personal V10. Cost alone is not acceptance; security, recovery, automation and reliability remain mandatory.

## Rejected for required OWNER phone path

### Tailscale Serve

Retained as a possible machine/CI technology, but rejected as the mandatory phone transport because normal tailnet access requires a device client, conflicting with the accepted browser-only requirement.

### Direct port forwarding / public Lenovo listener

Rejected. It creates an unnecessary public origin attack surface, depends on home-router/NAT configuration and weakens the intended replacement/recovery boundary.

### Cloudflare Quick Tunnel

Rejected for WP22A acceptance. Quick Tunnels are suitable for development/testing but are not the reviewed named-Tunnel, domain, Access-policy and recovery model required for production acceptance.

### New Render-hosted V10 Web App

Rejected. It would risk creating a competing runtime/data plane and moving private V10 state away from the Personal Node. The protected V9 `app:app` Render baseline remains separate and unchanged.

## Security consequences

Positive:

- no inbound public origin port;
- deny-before-origin Access layer;
- connector-side Access JWT validation;
- browser-only OWNER UX;
- source-controlled repeatable provider configuration after bootstrap;
- local durable/private state remains on the Personal Node.

Tradeoffs:

- remote availability depends on Cloudflare, DNS and the connector;
- an OWNER-controlled active Cloudflare zone/domain is required for the final named-host model;
- runtime Tunnel credentials must be separately reprovisioned on replacement nodes;
- `cloudflared` becomes part of the trusted local proxy chain and therefore must be versioned, supervised and tested.

## Automation decision

After unavoidable OWNER bootstrap, Cloudflare resources should be managed through reviewed Terraform/API from GitHub wherever practical. Long-lived credentials must be narrowly scoped and stored only in the approved GitHub Environment/secret boundary or runtime-only node store as appropriate. The Tunnel runtime credential is not a repository secret and must not appear in logs.

## Rollback

Disable/remove the Cloudflare published hostname/Tunnel connector and stop the WP22A remote runtime. The local/private Web, PostgreSQL state, Core, backups and V9 rollback remain intact. Rollback must not require data migration.

## Acceptance

This ADR becomes **ACCEPTED** only with the same exact-head evidence and post-merge sequence that accepts WP22A. Until then Cloudflare remains the selected implementation candidate, not an already accepted production dependency.
