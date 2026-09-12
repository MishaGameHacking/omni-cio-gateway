import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  CF_D_FUNCTION_PROVENANCE_CUSTODY_PATH,
  handleCfDFunctionProvenanceCustody,
} from "../../../cloudflare/src/cf-d-bootstrap-origin-custody.js";
import {
  CF_D_NEON_FUNCTION_PROVENANCE_INVALID,
  CF_D_NEON_FUNCTION_PROVENANCE_REDIRECT_REJECTED,
  CF_D_NEON_FUNCTION_PROVENANCE_RESPONSE_TOO_LARGE,
  fetchCfDNeonFunctionProvenance,
} from "../../../cloudflare/src/cf-d-neon-function-provenance.js";

const EXPECTED_SHA = "a".repeat(40);
const EXPECTED_DIGEST = "b".repeat(64);
const BRANCH_ID = "br-example1234";
const DATABASE_HOST = "ep-example1234.c-6.eu-central-1.aws.neon.tech";
const DATABASE_SQL_URL = `https://${DATABASE_HOST}/sql`;
const FUNCTION_ORIGIN =
  `https://${BRANCH_ID}-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech/`;
const RUNTIME_DSN =
  `postgresql://omni_cio_cloudflare_staging:${randomBytes(32).toString("base64url")}` +
  `@${DATABASE_HOST}/neondb?sslmode=require`;
const SYNC_TOKEN = "c".repeat(64);

function bindings(overrides = {}) {
  return {
    OMNI_V10_POSTGRES_DSN: RUNTIME_DSN,
    OMNI_V10_POSTGRES_RUNTIME_ROLE: "omni_cio_cloudflare_staging",
    OMNI_V10_CF_D_ORIGIN_SYNC_TOKEN: SYNC_TOKEN,
    ...overrides,
  };
}

function custodyRequest(options = {}) {
  const headers = new Headers({
    "x-omni-cf-d-origin-sync-token": options.token ?? SYNC_TOKEN,
    "x-omni-expected-sha": options.sha ?? EXPECTED_SHA,
  });
  return new Request(
    `https://example.workers.dev${CF_D_FUNCTION_PROVENANCE_CUSTODY_PATH}`,
    { method: options.method ?? "POST", headers },
  );
}

function functionResponse(options = {}) {
  const status = options.status ?? 200;
  const body =
    options.body ??
    (status === 405
      ? JSON.stringify({ status: "BLOCKED", code: "METHOD_NOT_ALLOWED" })
      : JSON.stringify({ status: "READY", source_sha256: EXPECTED_DIGEST }));
  return new Response(body, {
    status,
    headers: { "content-type": options.contentType ?? "application/json" },
  });
}

function networkDouble(options = {}) {
  const calls = [];
  const fetcher = async (request) => {
    calls.push(request);
    if (request.url === DATABASE_SQL_URL) {
      assert.equal(request.method, "POST");
      assert.equal(request.redirect, "manual");
      assert.equal(request.headers.get("neon-connection-string"), RUNTIME_DSN);
      return new Response(JSON.stringify({ rows: [[BRANCH_ID]] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (request.url === FUNCTION_ORIGIN) {
      assert.equal(request.method, "GET");
      assert.equal(request.redirect, "manual");
      assert.equal(request.headers.get("accept"), "application/json");
      assert.equal(request.headers.get("authorization"), null);
      assert.equal(request.headers.get("content-type"), null);
      assert.equal(request.headers.get("x-omni-expected-sha"), null);
      assert.equal(request.headers.get("x-omni-cf-d-origin-sync-token"), null);
      return options.functionResponse ?? functionResponse();
    }
    throw new Error(`unexpected egress: ${request.url}`);
  };
  return { calls, fetcher };
}

async function withFetch(fetcher, callback) {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = fetcher;
  try {
    return await callback();
  } finally {
    globalThis.fetch = originalFetch;
  }
}

test("CF-D provenance egress derives the same-branch Function and uses canonical GET root", async () => {
  const network = networkDouble();
  const digest = await withFetch(network.fetcher, () =>
    fetchCfDNeonFunctionProvenance(bindings()),
  );
  assert.equal(digest, EXPECTED_DIGEST);
  assert.equal(network.calls.length, 2);
  assert.equal(network.calls[0].url, DATABASE_SQL_URL);
  assert.equal(network.calls[1].url, FUNCTION_ORIGIN);
});

test("CF-D provenance egress treats only the exact legacy 405 contract as stale", async () => {
  const network = networkDouble({ functionResponse: functionResponse({ status: 405 }) });
  const digest = await withFetch(network.fetcher, () =>
    fetchCfDNeonFunctionProvenance(bindings()),
  );
  assert.equal(digest, null);

  const malformed = networkDouble({
    functionResponse: functionResponse({
      status: 405,
      body: JSON.stringify({ status: "BLOCKED", code: "OTHER" }),
    }),
  });
  await withFetch(malformed.fetcher, () =>
    assert.rejects(
      fetchCfDNeonFunctionProvenance(bindings()),
      new RegExp(CF_D_NEON_FUNCTION_PROVENANCE_INVALID),
    ),
  );
});

test("CF-D provenance egress fails closed on front-door status, redirect, and oversized body", async () => {
  const cases = [
    [
      functionResponse({ status: 403, body: JSON.stringify({ provider: "hidden" }) }),
      CF_D_NEON_FUNCTION_PROVENANCE_INVALID,
    ],
    [
      functionResponse({ status: 302, body: "{}" }),
      CF_D_NEON_FUNCTION_PROVENANCE_REDIRECT_REJECTED,
    ],
    [
      functionResponse({ body: "x".repeat(2_049) }),
      CF_D_NEON_FUNCTION_PROVENANCE_RESPONSE_TOO_LARGE,
    ],
  ];
  for (const [response, code] of cases) {
    const network = networkDouble({ functionResponse: response });
    await withFetch(network.fetcher, () =>
      assert.rejects(fetchCfDNeonFunctionProvenance(bindings()), new RegExp(code)),
    );
  }
});

test("CF-D provenance custody returns digest or legacy-stale state without provider destination", async () => {
  const exactNetwork = networkDouble();
  const exact = await withFetch(exactNetwork.fetcher, () =>
    handleCfDFunctionProvenanceCustody(
      custodyRequest(),
      bindings(),
      EXPECTED_SHA,
    ),
  );
  assert.equal(exact.status, 200);
  const exactPayload = await exact.json();
  assert.deepEqual(exactPayload, {
    status: "READY",
    source_sha: EXPECTED_SHA,
    source_state: "DIGEST",
    source_sha256: EXPECTED_DIGEST,
  });

  const legacyNetwork = networkDouble({
    functionResponse: functionResponse({ status: 405 }),
  });
  const legacy = await withFetch(legacyNetwork.fetcher, () =>
    handleCfDFunctionProvenanceCustody(
      custodyRequest(),
      bindings(),
      EXPECTED_SHA,
    ),
  );
  assert.equal(legacy.status, 200);
  assert.deepEqual(await legacy.json(), {
    status: "READY",
    source_sha: EXPECTED_SHA,
    source_state: "LEGACY_STALE",
    source_sha256: null,
  });
  assert.equal(JSON.stringify(exactPayload).includes("compute."), false);
});

test("CF-D provenance custody rejects unauthorized or non-staging requests before Neon egress", async () => {
  const cases = [
    [custodyRequest({ token: "d".repeat(64) }), bindings(), 403],
    [custodyRequest({ sha: "e".repeat(40) }), bindings(), 403],
    [custodyRequest({ method: "GET" }), bindings(), 403],
    [
      custodyRequest(),
      bindings({ OMNI_V10_POSTGRES_RUNTIME_ROLE: "omni_cio_cloudflare_prod" }),
      404,
    ],
  ];
  for (const [request, currentBindings, expectedStatus] of cases) {
    let calls = 0;
    const response = await withFetch(async () => {
      calls += 1;
      throw new Error("network must not be reached");
    }, () =>
      handleCfDFunctionProvenanceCustody(
        request,
        currentBindings,
        EXPECTED_SHA,
      ),
    );
    assert.equal(response.status, expectedStatus);
    assert.equal(calls, 0);
  }
});

test("CF-D provenance custody route is handled before the generic API/container proxy", async () => {
  const source = await readFile(
    new URL("../../../cloudflare/src/index.js", import.meta.url),
    "utf8",
  );
  const provenance = source.indexOf(
    "url.pathname === CF_D_FUNCTION_PROVENANCE_CUSTODY_PATH",
  );
  const genericApi = source.indexOf(
    'url.pathname === "/healthz" || url.pathname.startsWith("/api/")',
  );
  assert.ok(provenance >= 0);
  assert.ok(genericApi > provenance);
});
