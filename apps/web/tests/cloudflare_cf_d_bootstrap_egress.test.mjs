import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import test from "node:test";

import {
  CF_D_NEON_BOOTSTRAP_EGRESS_HOST,
  prepareCfDNeonBootstrapRequest,
} from "../../../cloudflare/src/cf-d-neon-bootstrap-egress.js";

const EXPECTED_SHA = "a".repeat(40);
const BRANCH_ID = "br-example1234";
const DATABASE_HOST = "ep-example1234.c-6.eu-central-1.aws.neon.tech";
const EXPECTED_FUNCTION_ORIGIN =
  `https://${BRANCH_ID}-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech/`;
const TEST_AUTHORIZATION = `Bearer ${randomBytes(32).toString("base64url")}`;
const TEST_RUNTIME_DSN =
  `postgresql://omni_cio_cloudflare_staging:${randomBytes(32).toString("base64url")}` +
  `@${DATABASE_HOST}/neondb?sslmode=require`;

function virtualRequest(options = {}) {
  const url = options.url ?? `http://${CF_D_NEON_BOOTSTRAP_EGRESS_HOST}/`;
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

function branchLookup(options = {}) {
  const status = options.status ?? 200;
  const branchId = options.branchId ?? BRANCH_ID;
  return async (request) => {
    assert.equal(request.url, `https://${DATABASE_HOST}/sql`);
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
    return new Response(
      JSON.stringify({ rows: [[branchId]] }),
      {
        status,
        headers: { "content-type": "application/json" },
      },
    );
  };
}

async function assertStopped(promise, code) {
  await assert.rejects(promise, (error) => {
    assert.ok(error instanceof Error);
    assert.equal(error.message, code);
    return true;
  });
}

test("CF-D trusted Worker resolves the Neon Function from its staging database binding", async () => {
  const prepared = await prepareCfDNeonBootstrapRequest(
    virtualRequest(),
    bindings(),
    EXPECTED_SHA,
    branchLookup(),
  );

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
    virtualRequest({ url: `https://${CF_D_NEON_BOOTSTRAP_EGRESS_HOST}/` }),
    virtualRequest({ url: "http://other.internal/" }),
    virtualRequest({ url: `http://${CF_D_NEON_BOOTSTRAP_EGRESS_HOST}:8080/` }),
    virtualRequest({ url: `http://${CF_D_NEON_BOOTSTRAP_EGRESS_HOST}/path` }),
    virtualRequest({ url: `http://${CF_D_NEON_BOOTSTRAP_EGRESS_HOST}/?query=1` }),
    virtualRequest({ legacyTarget: "https://example.com/" }),
    virtualRequest({ sha: "b".repeat(40) }),
  ];
  for (const request of rejected) {
    await assertStopped(
      prepareCfDNeonBootstrapRequest(
        request,
        bindings(),
        EXPECTED_SHA,
        branchLookup(),
      ),
      "CLOUDFLARE_CF_D_EGRESS_REQUEST_REJECTED",
    );
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
    await assertStopped(
      prepareCfDNeonBootstrapRequest(
        virtualRequest(),
        bindings(dsn),
        EXPECTED_SHA,
        branchLookup(),
      ),
      "CLOUDFLARE_CF_D_RUNTIME_DATABASE_INVALID",
    );
  }
});

test("CF-D Worker rejects failed or malformed branch metadata before provider egress", async () => {
  await assertStopped(
    prepareCfDNeonBootstrapRequest(
      virtualRequest(),
      bindings(),
      EXPECTED_SHA,
      branchLookup({ status: 503 }),
    ),
    "CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_FAILED",
  );
  await assertStopped(
    prepareCfDNeonBootstrapRequest(
      virtualRequest(),
      bindings(),
      EXPECTED_SHA,
      branchLookup({ branchId: "not-a-branch" }),
    ),
    "CLOUDFLARE_CF_D_NEON_BRANCH_RESPONSE_INVALID",
  );
});