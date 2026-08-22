# FL-033 — Render service name is not public-hostname authority

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 4; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-22**  
WP / reference: **WP22A Phase 4 Render + Neon synthetic preview / accepted main `3e6a50801e2ac8c75ab872a64d100a9a9424bc06`**

## Symptom / failing gate

The expected public preview address `https://omni-cio-v10-web.onrender.com` did not resolve as a working site after the PostgreSQL 18 bootstrap defect had been corrected and accepted.

The Phase 4 provisioner still contained a fixed `RENDER_SERVICE_URL` derived directly from the requested Render service name. It also rejected any provider-returned URL that did not equal that guessed address and used the guessed address for the external health probe.

## Root cause

Render separates the human/workspace service `name` from the provider-assigned globally unique public service slug. A service name needs to be unique within the workspace, while the public `onrender.com` hostname is provider-generated and may include a uniqueness suffix.

The provisioner violated that provider boundary in two directions:

1. it synthesized `https://<service-name>.onrender.com` instead of accepting the service's provider-assigned `slug` and `serviceDetails.url`;
2. it then used the synthesized address as both validation authority and network-probe target.

The hosted FastAPI runtime already used Render's `RENDER_EXTERNAL_HOSTNAME`, so the deployment producer and runtime consumer disagreed about which hostname was authoritative.

## Blast radius searched

The review covered:

- Render service creation and reuse responses;
- service name, slug and HTTPS URL validation;
- post-deploy exact-SHA wait logic;
- external `/healthz` probing;
- workflow output and public preview summary;
- hosted FastAPI `RENDER_EXTERNAL_HOSTNAME` consumption;
- deterministic Phase 4 deployment tests;
- Phase 4 implementation contract language;
- adjacent URL-confusion, redirect, path, credential, port and suffix-injection failure modes.

No Neon resource selection, PostgreSQL authority, broker authority, V9 production, public registration, paid resource or Real-execution boundary is expanded.

## Why preflight missed it

The original deterministic deployment test encoded the same incorrect assumption as the implementation: it required the public URL to equal the requested service name plus `.onrender.com`. Therefore the test protected a guessed provider behavior instead of the provider's returned identity fields.

The earlier deployment failures stopped before Render service provisioning, so the bad hostname assumption remained latent while PostgreSQL defects were being repaired.

## Corrective change

The Phase 4 provisioner now treats the Render service object as public-origin authority:

- require a strict DNS-safe provider `slug`;
- require `serviceDetails.url` to be HTTPS with no credentials, unsafe port, path, query or fragment;
- require the URL hostname to equal exactly `<slug>.onrender.com`;
- reject suffix-confusion and slug/URL mismatch;
- carry the validated provider URL into the external probe, workflow output and summary;
- require `/healthz` to report `database=READY` in addition to exact release identity and synthetic-preview state;
- keep the hosted runtime bound independently to `RENDER_EXTERNAL_HOSTNAME`.

The requested Render service name remains an expected configuration field, but it is no longer used to invent the public hostname.

## Permanent regression / guard

Deterministic Phase 4 tests now prove:

- a provider-assigned slug containing a uniqueness suffix is accepted;
- service name and public hostname are not conflated;
- wrong scheme, host, suffix, path or slug/URL mismatch fail closed;
- the hard-coded `RENDER_SERVICE_URL` authority cannot return;
- the external probe consumes `render_target.service_url`;
- the hosted application continues to consume `RENDER_EXTERNAL_HOSTNAME`;
- health acceptance requires `database=READY`.

## Future prevention rule

Do not synthesize provider-generated resource identifiers, slugs, hostnames or URLs from display names when the provider returns an authoritative identity field. Validate the returned identity structurally, bind related provider fields to each other, and propagate that validated value through all downstream consumers.

A deterministic test must model the provider's documented collision/uniqueness behavior rather than hard-code the first convenient happy-path identifier.
