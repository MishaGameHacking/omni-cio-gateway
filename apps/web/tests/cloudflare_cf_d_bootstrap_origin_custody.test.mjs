import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import test from "node:test";
import {
  CF_D_BOOTSTRAP_ORIGIN_CUSTODY_PATH,
  handleCfDBootstrapOriginCustody,
} from "../../../cloudflare/src/cf-d-bootstrap-origin-custody.js";

const EXPECTED_SHA = "a".repeat(40);
const BRANCH_ID = "br-example1234";
const DATABASE_HOST = "ep-example1234.c-6.eu-central-1.aws.neon.tech";
const DATABASE_SQL_URL = `https://${DATABASE_HOST}/sql`;
const EXPECTED_FUNCTION_ORIGIN =
  `https://${BRANCH_ID}-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech/`;
const TOKEN = "b".repeat(64);
const TEST_RUNTIME_DSN =
  `postgresql://omni_cio_cloudflare_staging:${randomBytes(32).toString("base64url")}` +
  `@${DATABASE_HOST}/neondb?sslmode=require`;

function bindings(overrides = {}) {
  return {
    OMNI_V10_POSTGRES_DSN: TEST_RUNTIME_DSN,
    OMNI_V10_POSTGRES_RUNTIME_ROLE: "omni_cio_cloudflare_staging",
    OMNI_V10_CF_D_ORIGIN_SYNC_TOKEN: TOKEN,
    ...overrides,
  };
}

function custodyRequest(options = {}) {
  return new Request(
    `https://example.workers.dev${CF_D_BOOTSTRAP_ORIGIN_CUSTODY_PATH}`,
    {
      method: options.method ?? "POST",
      headers: {
        "x-omni-cf-d-origin-sync-token": options.token ?? TOKEN,
        "x-omni-expected-sha": options.sha ?? EXPECTED_SHA,
      },
    },
  );
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

function branchLookupNetwork(options = {}) {
  const calls = [];
  const fetcher = async (request) => {
    calls.push(request);
    assert.equal(request.url, DATABASE_SQL_URL);
    assert.equal(request.method, "POST");
    assert.equal(request.redirect, "error");
    assert.equal(request.headers.get("neon-connection-string"), TEST_RUNTIME_DSN);
    const status = options.status ?? 200;
    const body = options.body ?? JSON.stringify({ rows: [[BRANCH_ID]] });
    return new Response(body, {
      status,
      headers: { "content-type": "application/json" },
    });
  };
  return { calls, fetcher };
}

test("authorized staging custody derives the exact same-cell function origin", async () => {
  const network = branchLookupNetwork();
  const response = await withFetch(network.fetcher, () =>
    handleCfDBootstrapOriginCustody(
      custodyRequest(),
      bindings(),
      EXPECTED_SHA,
    ),
  );
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.deepEqual(await response.json(), {
    status: "READY",
    source_sha: EXPECTED_SHA,
    bootstrap_origin: EXPECTED_FUNCTION_ORIGIN,
  });
  assert.equal(network.calls.length, 1);
});

test("custody rejects wrong token, SHA, method, and missing token before egress", async () => {
  const requests = [
    custodyRequest({ token: "c".repeat(64) }),
    custodyRequest({ sha: "d".repeat(40) }),
    custodyRequest({ method: "GET" }),
    new Request(
      `https://example.workers.dev${CF_D_BOOTSTRAP_ORIGIN_CUSTODY_PATH}`,
      { method: "POST", headers: { "x-omni-expected-sha": EXPECTED_SHA } },
    ),
  ];
  for (const current of requests) {
    const network = branchLookupNetwork();
    const response = await withFetch(network.fetcher, () =>
      handleCfDBootstrapOriginCustody(current, bindings(), EXPECTED_SHA),
    );
    assert.equal(response.status, 403);
    assert.equal(network.calls.length, 0);
  }
});

test("custody is invisible outside the staging runtime role", async () => {
  const network = branchLookupNetwork();
  const response = await withFetch(network.fetcher, () =>
    handleCfDBootstrapOriginCustody(
      custodyRequest(),
      bindings({ OMNI_V10_POSTGRES_RUNTIME_ROLE: "omni_cio_cloudflare_prod" }),
      EXPECTED_SHA,
    ),
  );
  assert.equal(response.status, 404);
  assert.equal(network.calls.length, 0);
});

test("custody fails closed when branch proof is unavailable or malformed", async () => {
  for (const options of [
    { status: 503 },
    { body: JSON.stringify({ rows: [["not-a-branch"]] }) },
    { body: JSON.stringify({ rows: [[`br-${"a".repeat(57)}`]] }) },
  ]) {
    const network = branchLookupNetwork(options);
    const response = await withFetch(network.fetcher, () =>
      handleCfDBootstrapOriginCustody(
        custodyRequest(),
        bindings(),
        EXPECTED_SHA,
      ),
    );
    assert.equal(response.status, 502);
    const payload = await response.json();
    assert.deepEqual(payload, {
      detail: "CLOUDFLARE_CF_D_ORIGIN_SYNC_DERIVATION_FAILED",
    });
    assert.equal(payload.bootstrap_origin, undefined);
  }
});
