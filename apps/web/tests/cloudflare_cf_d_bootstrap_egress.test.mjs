import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import test from "node:test";

import {
  CF_D_NEON_BOOTSTRAP_EGRESS_HOST,
  fetchCfDNeonBootstrap,
  fetchCfDTrustedNeonRequest,
  prepareCfDNeonBootstrapRequest,
} from "../../../cloudflare/src/cf-d-neon-bootstrap-egress.js";

const EXPECTED_SHA = "a".repeat(40);
const BRANCH_ID = "br-example1234";
const DATABASE_HOST = "ep-example1234.c-6.eu-central-1.aws.neon.tech";
const DATABASE_SQL_URL = `https://${DATABASE_HOST}/sql`;
const EXPECTED_FUNCTION_ORIGIN =
  `https://${BRANCH_ID}-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech/`;
const TEST_AUTHORIZATION = `Bearer ${randomBytes(32).toString("base64url")}`;
const TEST_RUNTIME_DSN =
  `postgresql://omni_cio_cloudflare_staging:${randomBytes(32).toString("base64url")}` +
  `@${DATABASE_HOST}/neondb?sslmode=require`;

function virtualRequest(options = {}) {
  const url = options.url ?? `https://${CF_D_NEON_BOOTSTRAP_EGRESS_HOST}/`;
  const method = options.method ?? "POST";
  const headers = new Headers({
    Authorization: TEST_AUTHORIZATION,
    "Content-Type": "application/json",
  });
  if (options.legacyTarget !== undefined) {
    headers.set("x-omni-neon-bootstrap-target", options.legacyTarget);
  }
  const init = { method, headers };
  if (method !== "GET" && method !== "HEAD") {
    init.body = JSON.stringify({ expected_sha: options.sha ?? EXPECTED_SHA });
    init.duplex = "half";
  }
  return new Request(url, init);
}

function bindings(dsn = TEST_RUNTIME_DSN) {
  return { OMNI_V10_POSTGRES_DSN: dsn };
}

function networkDouble(options = {}) {
  const branchStatus = options.branchStatus ?? 200;
  const branchId = options.branchId ?? BRANCH_ID;
  const branchBody =
    options.branchBody ?? JSON.stringify({ rows: [[branchId]] });
  const functionStatus = options.functionStatus ?? 200;
  const calls = [];
  const fetcher = async (request) => {
    calls.push(request);
    if (request.url === DATABASE_SQL_URL) {
      assert.equal(request.method, "POST");
      assert.equal(request.redirect, "error");
      assert.equal(
        request.headers.get("neon-connection-string"),
        TEST_RUNTIME_DSN,
      );
      assert.deepEqual(await request.json(), {
        query: "SELECT current_setting('neon.branch_id', true)",
        params: [],
      });
      return new Response(branchBody, {
        status: branchStatus,
        headers: { "content-type": "application/json" },
      });
    }
    if (request.url === EXPECTED_FUNCTION_ORIGIN) {
      assert.equal(request.method, "POST");
      assert.equal(request.redirect, "manual");
      assert.equal(request.headers.get("authorization"), TEST_AUTHORIZATION);
      assert.deepEqual(await request.json(), { expected_sha: EXPECTED_SHA });
      return new Response(JSON.stringify({ status: "READY" }), {
        status: functionStatus,
        headers: { "content-type": "application/json" },
      });
    }
    throw new Error(`unexpected test egress: ${request.url}`);
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

async function assertStopped(promise, code) {
  await assert.rejects(promise, (error) => {
    assert.ok(error instanceof Error);
    assert.equal(error.message, code);
    return true;
  });
}

test("CF-D trusted Worker resolves and invokes the Neon Function from its staging database binding", async () => {
  const network = networkDouble();
  const response = await withFetch(network.fetcher, () =>
    fetchCfDNeonBootstrap(virtualRequest(), bindings(), EXPECTED_SHA),
  );

  assert.equal(response.status, 200);
  assert.equal(network.calls.length, 2);
  assert.equal(network.calls[0].url, DATABASE_SQL_URL);
  assert.equal(network.calls[1].url, EXPECTED_FUNCTION_ORIGIN);
  assert.equal(network.calls[1].headers.get("x-omni-neon-bootstrap-target"), null);
  assert.equal(network.calls[1].headers.get("host"), null);
});

test("CF-D preparation reconstructs a bounded provider request", async () => {
  const network = networkDouble();
  const prepared = await withFetch(network.fetcher, () =>
    prepareCfDNeonBootstrapRequest(
      virtualRequest(),
      bindings(),
      EXPECTED_SHA,
    ),
  );

  assert.equal(network.calls.length, 1);
  assert.equal(prepared.url, EXPECTED_FUNCTION_ORIGIN);
  assert.equal(prepared.method, "POST");
  assert.equal(prepared.redirect, "manual");
  assert.equal(prepared.headers.get("authorization"), TEST_AUTHORIZATION);
  assert.equal(prepared.headers.get("x-omni-neon-bootstrap-target"), null);
  assert.equal(prepared.headers.get("host"), null);
  assert.deepEqual(await prepared.json(), { expected_sha: EXPECTED_SHA });
});

test("CF-D virtual request cannot select an external target or broaden the route", async () => {
  const rejected = [
    virtualRequest({ method: "GET" }),
    virtualRequest({ url: `http://${CF_D_NEON_BOOTSTRAP_EGRESS_HOST}/` }),
    virtualRequest({ url: "https://other.internal/" }),
    virtualRequest({ url: `https://${CF_D_NEON_BOOTSTRAP_EGRESS_HOST}:8443/` }),
    virtualRequest({ url: `https://${CF_D_NEON_BOOTSTRAP_EGRESS_HOST}/path` }),
    virtualRequest({ url: `https://${CF_D_NEON_BOOTSTRAP_EGRESS_HOST}/?query=1` }),
    virtualRequest({ legacyTarget: "https://example.com/" }),
    virtualRequest({ sha: "b".repeat(40) }),
  ];
  for (const request of rejected) {
    const network = networkDouble();
    await withFetch(network.fetcher, () =>
      assertStopped(
        prepareCfDNeonBootstrapRequest(
          request,
          bindings(),
          EXPECTED_SHA,
        ),
        "CLOUDFLARE_CF_D_EGRESS_REQUEST_REJECTED",
      ),
    );
    assert.equal(network.calls.length, 0);
  }
});

test("CF-D Worker rejects non-staging or non-Frankfurt runtime database bindings", async () => {
  const invalidDsns = [
    `http://omni_cio_cloudflare_staging:${randomBytes(16).toString("hex")}@${DATABASE_HOST}/neondb?sslmode=require`,
    `postgresql://omni_cio_cloudflare_prod:${randomBytes(16).toString("hex")}@${DATABASE_HOST}/neondb?sslmode=require`,
    `postgresql://omni_cio_cloudflare_staging:${randomBytes(16).toString("hex")}@example.com/neondb?sslmode=require`,
    `postgresql://omni_cio_cloudflare_staging:${randomBytes(16).toString("hex")}@ep-example.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require`,
    `postgresql://omni_cio_cloudflare_staging:${randomBytes(16).toString("hex")}@${DATABASE_HOST}/neondb?sslmode=disable`,
  ];
  for (const dsn of invalidDsns) {
    const network = networkDouble();
    await withFetch(network.fetcher, () =>
      assertStopped(
        prepareCfDNeonBootstrapRequest(
          virtualRequest(),
          bindings(dsn),
          EXPECTED_SHA,
        ),
        "CLOUDFLARE_CF_D_RUNTIME_DATABASE_INVALID",
      ),
    );
    assert.equal(network.calls.length, 0);
  }
});

test("CF-D Worker rejects failed, oversized, or malformed branch metadata before Function egress", async () => {
  const failedLookup = networkDouble({ branchStatus: 503 });
  await withFetch(failedLookup.fetcher, () =>
    assertStopped(
      prepareCfDNeonBootstrapRequest(
        virtualRequest(),
        bindings(),
        EXPECTED_SHA,
      ),
      "CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_FAILED",
    ),
  );
  assert.equal(failedLookup.calls.length, 1);

  const oversizedLookup = networkDouble({ branchBody: "x".repeat(8_193) });
  await withFetch(oversizedLookup.fetcher, () =>
    assertStopped(
      prepareCfDNeonBootstrapRequest(
        virtualRequest(),
        bindings(),
        EXPECTED_SHA,
      ),
      "CLOUDFLARE_CF_D_NEON_BRANCH_RESPONSE_TOO_LARGE",
    ),
  );
  assert.equal(oversizedLookup.calls.length, 1);

  const invalidJsonLookup = networkDouble({ branchBody: "{" });
  await withFetch(invalidJsonLookup.fetcher, () =>
    assertStopped(
      prepareCfDNeonBootstrapRequest(
        virtualRequest(),
        bindings(),
        EXPECTED_SHA,
      ),
      "CLOUDFLARE_CF_D_NEON_BRANCH_RESPONSE_INVALID",
    ),
  );
  assert.equal(invalidJsonLookup.calls.length, 1);

  const malformedLookup = networkDouble({ branchId: "not-a-branch" });
  await withFetch(malformedLookup.fetcher, () =>
    assertStopped(
      prepareCfDNeonBootstrapRequest(
        virtualRequest(),
        bindings(),
        EXPECTED_SHA,
      ),
      "CLOUDFLARE_CF_D_NEON_BRANCH_RESPONSE_INVALID",
    ),
  );
  assert.equal(malformedLookup.calls.length, 1);
});

test("CF-D network sink rejects forged Neon destinations before fetch", async () => {
  const databaseRequests = [
    new Request("https://example.com/sql", { method: "POST" }),
    new Request(`http://${DATABASE_HOST}/sql`, { method: "POST" }),
    new Request(`https://${DATABASE_HOST}:444/sql`, { method: "POST" }),
    new Request(`https://${DATABASE_HOST}/other`, { method: "POST" }),
    new Request(`https://${DATABASE_HOST}/sql?query=1`, { method: "POST" }),
  ];
  const functionRequests = [
    new Request("https://example.com/", { method: "POST" }),
    new Request(
      `https://${BRANCH_ID}-other.compute.c-6.eu-central-1.aws.neon.tech/`,
      { method: "POST" },
    ),
    new Request(
      `https://${BRANCH_ID}-cfdprodbootstrap.compute.c-6.us-east-1.aws.neon.tech/`,
      { method: "POST" },
    ),
    new Request(`${EXPECTED_FUNCTION_ORIGIN}path`, { method: "POST" }),
    new Request(`${EXPECTED_FUNCTION_ORIGIN}?query=1`, { method: "POST" }),
  ];
  const network = networkDouble();
  await withFetch(network.fetcher, async () => {
    for (const request of databaseRequests) {
      await assertStopped(
        fetchCfDTrustedNeonRequest(request, "database"),
        "CLOUDFLARE_CF_D_NEON_DESTINATION_REJECTED",
      );
    }
    for (const request of functionRequests) {
      await assertStopped(
        fetchCfDTrustedNeonRequest(request, "function"),
        "CLOUDFLARE_CF_D_NEON_DESTINATION_REJECTED",
      );
    }
    await assertStopped(
      fetchCfDTrustedNeonRequest(
        new Request(DATABASE_SQL_URL, { method: "POST" }),
        "unknown",
      ),
      "CLOUDFLARE_CF_D_NEON_DESTINATION_REJECTED",
    );
  });
  assert.equal(network.calls.length, 0);
});
