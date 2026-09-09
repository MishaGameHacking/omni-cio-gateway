import assert from "node:assert/strict";
import test from "node:test";

import {
  CF_D_GITHUB_OIDC_HEADER,
  CF_D_PRODUCTION_DATABASE_BOOTSTRAP_PATH,
  cfDProductionBootstrapIngressFailure,
  prepareCfDProductionBootstrapIngress,
} from "../../../cloudflare/src/cf-d-production-bootstrap-ingress.js";

const EXPECTED_SHA = "a".repeat(40);
const TEST_OIDC = "synthetic_header.synthetic_claims.synthetic_signature";

function ingressRequest(options = {}) {
  const headers = new Headers({
    "content-type": "application/json",
    "x-omni-expected-sha": options.sha ?? EXPECTED_SHA,
  });
  if (options.oidc !== false) {
    headers.set(CF_D_GITHUB_OIDC_HEADER, options.oidc ?? TEST_OIDC);
  }
  if (options.authorization) {
    headers.set("authorization", options.authorization);
  }
  const method = options.method ?? "POST";
  const init = { method, headers };
  if (method !== "GET" && method !== "HEAD") {
    init.body = JSON.stringify({ expected_sha: EXPECTED_SHA });
    init.duplex = "half";
  }
  return new Request(
    `https://example.workers.dev${options.path ?? CF_D_PRODUCTION_DATABASE_BOOTSTRAP_PATH}`,
    init,
  );
}

test("CF-D trusted ingress materializes Bearer only inside Worker", async () => {
  const prepared = prepareCfDProductionBootstrapIngress(
    ingressRequest(),
    EXPECTED_SHA,
  );
  assert.equal(prepared.headers.get(CF_D_GITHUB_OIDC_HEADER), null);
  assert.equal(prepared.headers.get("authorization"), `Bearer ${TEST_OIDC}`);
  assert.equal(prepared.headers.get("x-omni-expected-sha"), EXPECTED_SHA);
  assert.deepEqual(await prepared.json(), { expected_sha: EXPECTED_SHA });
});

test("CF-D trusted ingress rejects public Authorization and malformed OIDC", () => {
  const rejected = [
    ingressRequest({ authorization: `Bearer ${TEST_OIDC}` }),
    ingressRequest({ oidc: "not-a-jwt" }),
    ingressRequest({ oidc: false }),
  ];
  for (const request of rejected) {
    assert.throws(
      () => prepareCfDProductionBootstrapIngress(request, EXPECTED_SHA),
      (error) => {
        const failure = cfDProductionBootstrapIngressFailure(error);
        assert.deepEqual(failure, {
          detail: "CLOUDFLARE_CF_D_OIDC_REQUIRED",
          status: 401,
        });
        assert.equal(JSON.stringify(failure).includes(TEST_OIDC), false);
        return true;
      },
    );
  }
});

test("CF-D trusted ingress rejects method, path, and exact-SHA drift", () => {
  const rejected = [
    ingressRequest({ method: "GET" }),
    ingressRequest({ path: "/api/internal/v10/cf-d/other" }),
    ingressRequest({ sha: "b".repeat(40) }),
  ];
  for (const request of rejected) {
    assert.throws(
      () => prepareCfDProductionBootstrapIngress(request, EXPECTED_SHA),
      (error) => {
        assert.deepEqual(cfDProductionBootstrapIngressFailure(error), {
          detail: "CLOUDFLARE_CF_D_EXPECTED_SHA_INVALID",
          status: 403,
        });
        return true;
      },
    );
  }
});
