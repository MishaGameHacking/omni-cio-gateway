import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import test from "node:test";

import {
  CF_D_BOOTSTRAP_ORIGIN_CUSTODY_PATH,
  handleCfDBootstrapOriginCustody,
} from "../../../cloudflare/src/cf-d-bootstrap-origin-custody.js";
import {
  CF_D_NEON_BOOTSTRAP_EGRESS_HOST,
  fetchCfDNeonBootstrap,
  prepareCfDNeonBootstrapRequest,
  sanitizedCfDDerivationFailureCode,
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
const TEST_SYNC_TOKEN = "b".repeat(64);

function virtualRequest(options = {}) {
  const url = options.url ?? `https://${CF_D_NEON_BOOTSTRAP_EGRESS_HOST}/`;
  const method = options.method ?? "POST";
  const headers = new Headers({
    Authorization: TEST_AUTHORIZATION,
    "Content-Type": "application/json",
    "X-Untrusted-Forward": "must-not-leave-worker",
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

function bindings(
  dsn = TEST_RUNTIME_DSN,
  origin = EXPECTED_FUNCTION_ORIGIN,
) {
  return {
    OMNI_V10_POSTGRES_DSN: dsn,
    OMNI_V10_CF_D_NEON_BOOTSTRAP_ORIGIN: origin,
  };
}

function custodyBindings(overrides = {}) {
  return {
    ...bindings(),
    OMNI_V10_POSTGRES_RUNTIME_ROLE: "omni_cio_cloudflare_staging",
    OMNI_V10_CF_D_ORIGIN_SYNC_TOKEN: TEST_SYNC_TOKEN,
    ...overrides,
  };
}

function custodyRequest(options = {}) {
  const headers = new Headers();
  if (options.includeToken !== false) {
    headers.set(
      "x-omni-cf-d-origin-sync-token",
      options.token ?? TEST_SYNC_TOKEN,
    );
  }
  headers.set("x-omni-expected-sha", options.sha ?? EXPECTED_SHA);
  return new Request(
    `https://example.workers.dev${CF_D_BOOTSTRAP_ORIGIN_CUSTODY_PATH}`,
    { method: options.method ?? "POST", headers },
  );
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
      assert.equal(request.headers.get("x-untrusted-forward"), null);
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
      assert.equal(request.headers.get("x-untrusted-forward"), null);
      assert.equal(request.headers.get("x-omni-neon-bootstrap-target"), null);
      assert.equal(request.headers.get("host"), null);
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

test("CF-D trusted Worker invokes only the secret-bound same-branch Neon Function", async () => {
  const network = networkDouble();
  const response = await withFetch(network.fetcher, () =>
    fetchCfDNeonBootstrap(virtualRequest(), bindings(), EXPECTED_SHA),
  );

  assert.equal(response.status, 200);
  assert.equal(network.calls.length, 2);
  assert.equal(network.calls[0].url, DATABASE_SQL_URL);
  assert.equal(network.calls[1].url, EXPECTED_FUNCTION_ORIGIN);
});

test("CF-D preparation reconstructs a bounded provider request from secret custody", async () => {
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
  assert.equal(prepared.headers.get("x-untrusted-forward"), null);
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

test("CF-D Worker requires a secret-bound Function origin matching database cell and branch", async () => {
  const invalidBeforeLookup = [
    undefined,
    "https://example.com/",
    `http://${BRANCH_ID}-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech/`,
    `https://${BRANCH_ID}-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech:444/`,
    `${EXPECTED_FUNCTION_ORIGIN}path`,
    `${EXPECTED_FUNCTION_ORIGIN}?query=1`,
  ];
  for (const origin of invalidBeforeLookup) {
    const network = networkDouble();
    const currentBindings =
      origin === undefined
        ? { OMNI_V10_POSTGRES_DSN: TEST_RUNTIME_DSN }
        : bindings(TEST_RUNTIME_DSN, origin);
    await withFetch(network.fetcher, () =>
      assertStopped(
        prepareCfDNeonBootstrapRequest(
          virtualRequest(),
          currentBindings,
          EXPECTED_SHA,
        ),
        "CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_INVALID",
      ),
    );
    assert.equal(network.calls.length, 0);
  }

  const wrongCell = networkDouble();
  await withFetch(wrongCell.fetcher, () =>
    assertStopped(
      prepareCfDNeonBootstrapRequest(
        virtualRequest(),
        bindings(
          TEST_RUNTIME_DSN,
          `https://${BRANCH_ID}-cfdprodbootstrap.compute.c-9.eu-central-1.aws.neon.tech/`,
        ),
        EXPECTED_SHA,
      ),
      "CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_MISMATCH",
    ),
  );
  assert.equal(wrongCell.calls.length, 0);

  const wrongBranch = networkDouble();
  await withFetch(wrongBranch.fetcher, () =>
    assertStopped(
      prepareCfDNeonBootstrapRequest(
        virtualRequest(),
        bindings(
          TEST_RUNTIME_DSN,
          "https://br-other1234-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech/",
        ),
        EXPECTED_SHA,
      ),
      "CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_MISMATCH",
    ),
  );
  assert.equal(wrongBranch.calls.length, 1);
  assert.equal(wrongBranch.calls[0].url, DATABASE_SQL_URL);
});

test("CF-D Worker classifies branch HTTP failure without provider body leakage", async () => {
  const cases = [
    [401, "CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_UNAUTHORIZED"],
    [403, "CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_UNAUTHORIZED"],
    [404, "CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_NOT_FOUND"],
    [503, "CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_NOT_READY"],
    [418, "CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_HTTP_STATUS_INVALID"],
  ];
  for (const [branchStatus, code] of cases) {
    const network = networkDouble({
      branchStatus,
      branchBody: JSON.stringify({ ignored: "provider-response-not-propagated" }),
    });
    await withFetch(network.fetcher, () =>
      assertStopped(
        prepareCfDNeonBootstrapRequest(
          virtualRequest(),
          bindings(),
          EXPECTED_SHA,
        ),
        code,
      ),
    );
    assert.equal(network.calls.length, 1);
  }
});

test("CF-D Worker rejects oversized or malformed branch metadata before Function egress", async () => {
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

test("CF-D origin custody derives the exact same-cell function origin", async () => {
  const network = networkDouble();
  const response = await withFetch(network.fetcher, () =>
    handleCfDBootstrapOriginCustody(
      custodyRequest(),
      custodyBindings(),
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

test("CF-D origin custody rejects unauthorized requests before egress", async () => {
  const requests = [
    custodyRequest({ token: "c".repeat(64) }),
    custodyRequest({ sha: "d".repeat(40) }),
    custodyRequest({ method: "GET" }),
    custodyRequest({ includeToken: false }),
  ];
  for (const request of requests) {
    const network = networkDouble();
    const response = await withFetch(network.fetcher, () =>
      handleCfDBootstrapOriginCustody(
        request,
        custodyBindings(),
        EXPECTED_SHA,
      ),
    );
    assert.equal(response.status, 403);
    assert.equal(network.calls.length, 0);
  }
});

test("CF-D origin custody is invisible outside the staging runtime role", async () => {
  const network = networkDouble();
  const response = await withFetch(network.fetcher, () =>
    handleCfDBootstrapOriginCustody(
      custodyRequest(),
      custodyBindings({
        OMNI_V10_POSTGRES_RUNTIME_ROLE: "omni_cio_cloudflare_prod",
      }),
      EXPECTED_SHA,
    ),
  );

  assert.equal(response.status, 404);
  assert.equal(network.calls.length, 0);
});

test("CF-D derivation sanitizer exposes only allowlisted diagnostic codes", () => {
  const allowed = [
    "CLOUDFLARE_CF_D_RUNTIME_DATABASE_INVALID",
    "CLOUDFLARE_CF_D_NEON_DESTINATION_REJECTED",
    "CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_FAILED",
    "CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_UNAUTHORIZED",
    "CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_NOT_FOUND",
    "CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_NOT_READY",
    "CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_HTTP_STATUS_INVALID",
    "CLOUDFLARE_CF_D_NEON_BRANCH_RESPONSE_TOO_LARGE",
    "CLOUDFLARE_CF_D_NEON_BRANCH_RESPONSE_INVALID",
    "CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_INVALID",
    "CLOUDFLARE_CF_D_BOOTSTRAP_ORIGIN_MISMATCH",
  ];
  for (const code of allowed) {
    assert.equal(sanitizedCfDDerivationFailureCode(new Error(code)), code);
  }
  assert.equal(
    sanitizedCfDDerivationFailureCode(new Error("UNTRUSTED_INTERNAL_DETAIL")),
    "CLOUDFLARE_CF_D_ORIGIN_SYNC_DERIVATION_FAILED",
  );
  assert.equal(
    sanitizedCfDDerivationFailureCode("UNTRUSTED_INTERNAL_DETAIL"),
    "CLOUDFLARE_CF_D_ORIGIN_SYNC_DERIVATION_FAILED",
  );
});

test("CF-D origin custody preserves sanitized branch failure classes", async () => {
  const cases = [
    [
      { branchStatus: 403 },
      "CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_UNAUTHORIZED",
    ],
    [
      { branchStatus: 404 },
      "CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_NOT_FOUND",
    ],
    [
      { branchStatus: 503 },
      "CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_NOT_READY",
    ],
    [
      { branchStatus: 418 },
      "CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_HTTP_STATUS_INVALID",
    ],
    [
      { branchId: "not-a-branch" },
      "CLOUDFLARE_CF_D_NEON_BRANCH_RESPONSE_INVALID",
    ],
    [
      { branchId: `br-${"a".repeat(57)}` },
      "CLOUDFLARE_CF_D_NEON_BRANCH_RESPONSE_INVALID",
    ],
  ];
  for (const [options, detail] of cases) {
    const network = networkDouble(options);
    const response = await withFetch(network.fetcher, () =>
      handleCfDBootstrapOriginCustody(
        custodyRequest(),
        custodyBindings(),
        EXPECTED_SHA,
      ),
    );
    assert.equal(response.status, 502);
    assert.deepEqual(await response.json(), { detail });
  }
});

test("CF-D origin custody classifies branch transport failure without detail leakage", async () => {
  const response = await withFetch(
    async () => {
      throw new Error("SIMULATED_TRANSPORT_FAILURE");
    },
    () =>
      handleCfDBootstrapOriginCustody(
        custodyRequest(),
        custodyBindings(),
        EXPECTED_SHA,
      ),
  );
  assert.equal(response.status, 502);
  assert.deepEqual(await response.json(), {
    detail: "CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_FAILED",
  });
});
