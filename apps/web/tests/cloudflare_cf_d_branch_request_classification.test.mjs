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
const TEST_RUNTIME_DSN =
  `postgresql://omni_cio_cloudflare_staging:${randomBytes(32).toString("base64url")}` +
  `@${DATABASE_HOST}/neondb?sslmode=require`;
const EXPECTED_FUNCTION_ORIGIN =
  `https://${BRANCH_ID}-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech/`;
const TEST_SYNC_TOKEN = "b".repeat(64);

function custodyRequest() {
  return new Request(
    `https://example.workers.dev${CF_D_BOOTSTRAP_ORIGIN_CUSTODY_PATH}`,
    {
      method: "POST",
      headers: {
        "x-omni-cf-d-origin-sync-token": TEST_SYNC_TOKEN,
        "x-omni-expected-sha": EXPECTED_SHA,
      },
    },
  );
}

function custodyBindings() {
  return {
    OMNI_V10_POSTGRES_DSN: TEST_RUNTIME_DSN,
    OMNI_V10_CF_D_NEON_BOOTSTRAP_ORIGIN: EXPECTED_FUNCTION_ORIGIN,
    OMNI_V10_POSTGRES_RUNTIME_ROLE: "omni_cio_cloudflare_staging",
    OMNI_V10_CF_D_ORIGIN_SYNC_TOKEN: TEST_SYNC_TOKEN,
  };
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

async function withRequestConstructor(requestConstructor, callback) {
  const originalRequest = globalThis.Request;
  globalThis.Request = requestConstructor;
  try {
    return await callback();
  } finally {
    globalThis.Request = originalRequest;
  }
}

test("CF-D origin custody classifies branch request construction failure before transport", async () => {
  const request = custodyRequest();
  let fetchCalls = 0;
  const response = await withFetch(
    async () => {
      fetchCalls += 1;
      throw new Error("NETWORK_MUST_NOT_BE_REACHED");
    },
    () =>
      withRequestConstructor(
        class RejectingRequest {
          constructor() {
            throw new Error("UNTRUSTED_REQUEST_CONSTRUCTION_DETAIL");
          }
        },
        () =>
          handleCfDBootstrapOriginCustody(
            request,
            custodyBindings(),
            EXPECTED_SHA,
          ),
      ),
  );

  assert.equal(fetchCalls, 0);
  assert.equal(response.status, 502);
  assert.deepEqual(await response.json(), {
    detail: "CLOUDFLARE_CF_D_NEON_BRANCH_REQUEST_INVALID",
  });
});
