import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import test from "node:test";

import {
  CF_D_NEON_BOOTSTRAP_EGRESS_HOST,
  CF_D_NEON_BOOTSTRAP_TARGET_HEADER,
  prepareCfDNeonBootstrapRequest,
  validatedCfDNeonBootstrapTarget,
} from "../../../cloudflare/src/cf-d-neon-bootstrap-egress.js";

const VALID_TARGET =
  "https://br-example1234-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech/";
const EXPECTED_SHA = "a".repeat(40);
const TEST_AUTHORIZATION = `Bearer ${randomBytes(32).toString("base64url")}`;

function virtualRequest(options = {}) {
  const url = options.url ?? `http://${CF_D_NEON_BOOTSTRAP_EGRESS_HOST}/`;
  const method = options.method ?? "POST";
  const target = Object.hasOwn(options, "target") ? options.target : VALID_TARGET;
  const headers = new Headers({
    Authorization: TEST_AUTHORIZATION,
    "Content-Type": "application/json",
    Host: CF_D_NEON_BOOTSTRAP_EGRESS_HOST,
  });
  if (target !== undefined) {
    headers.set(CF_D_NEON_BOOTSTRAP_TARGET_HEADER, target);
  }
  const init = { method, headers };
  if (method !== "GET" && method !== "HEAD") {
    init.body = JSON.stringify({ expected_sha: EXPECTED_SHA });
    init.duplex = "half";
  }
  return new Request(url, init);
}

function assertStopped(callback, code) {
  assert.throws(callback, (error) => {
    assert.ok(error instanceof Error);
    assert.equal(error.message, code);
    return true;
  });
}

test("CF-D valid target is canonicalized to the dedicated Frankfurt Neon Function", () => {
  assert.equal(validatedCfDNeonBootstrapTarget(VALID_TARGET), VALID_TARGET);
  assert.equal(
    validatedCfDNeonBootstrapTarget(
      "https://BR-EXAMPLE1234-CFDPRODBOOTSTRAP.COMPUTE.C-6.EU-CENTRAL-1.AWS.NEON.TECH/",
    ),
    VALID_TARGET,
  );
});

test("CF-D target allowlist rejects arbitrary or structurally broadened destinations", () => {
  const rejected = [
    "https://example.com/",
    "http://br-example1234-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech/",
    "https://br-example1234-other.compute.c-6.eu-central-1.aws.neon.tech/",
    "https://br-example1234-cfdprodbootstrap.compute.c-9.us-east-1.aws.neon.tech/",
    "https://user@br-example1234-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech/",
    "https://br-example1234-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech:444/",
    "https://br-example1234-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech/path",
    "https://br-example1234-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech/?query=1",
    "https://br-example1234-cfdprodbootstrap.compute.c-6.eu-central-1.aws.neon.tech/#fragment",
    "not-a-url",
    "",
  ];
  for (const target of rejected) {
    assertStopped(
      () => validatedCfDNeonBootstrapTarget(target),
      "CLOUDFLARE_CF_D_NEON_TARGET_INVALID",
    );
  }
});

test("CF-D virtual egress request rejects route and method broadening", () => {
  const rejected = [
    virtualRequest({ method: "GET" }),
    virtualRequest({ url: `https://${CF_D_NEON_BOOTSTRAP_EGRESS_HOST}/` }),
    virtualRequest({ url: "http://other.internal/" }),
    virtualRequest({ url: `http://${CF_D_NEON_BOOTSTRAP_EGRESS_HOST}:8080/` }),
    virtualRequest({ url: `http://${CF_D_NEON_BOOTSTRAP_EGRESS_HOST}/path` }),
    virtualRequest({ url: `http://${CF_D_NEON_BOOTSTRAP_EGRESS_HOST}/?query=1` }),
  ];
  for (const request of rejected) {
    assertStopped(
      () => prepareCfDNeonBootstrapRequest(request),
      "CLOUDFLARE_CF_D_EGRESS_REQUEST_REJECTED",
    );
  }
});

test("CF-D prepared provider request strips internal routing authority", async () => {
  const source = virtualRequest();
  const prepared = prepareCfDNeonBootstrapRequest(source);

  assert.equal(prepared.url, VALID_TARGET);
  assert.equal(prepared.method, "POST");
  assert.equal(prepared.redirect, "manual");
  assert.equal(prepared.headers.get("authorization"), TEST_AUTHORIZATION);
  assert.equal(prepared.headers.get(CF_D_NEON_BOOTSTRAP_TARGET_HEADER), null);
  assert.equal(prepared.headers.get("host"), null);
  assert.deepEqual(await prepared.json(), { expected_sha: EXPECTED_SHA });
});

test("CF-D prepared request rejects a missing or malicious target header", () => {
  assertStopped(
    () => prepareCfDNeonBootstrapRequest(virtualRequest({ target: undefined })),
    "CLOUDFLARE_CF_D_NEON_TARGET_INVALID",
  );
  assertStopped(
    () =>
      prepareCfDNeonBootstrapRequest(
        virtualRequest({ target: "https://example.com/" }),
      ),
    "CLOUDFLARE_CF_D_NEON_TARGET_INVALID",
  );
});
