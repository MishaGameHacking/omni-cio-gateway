import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  CF_D_SANITIZED_DERIVATION_FAILURE_CODES,
  sanitizedCfDDerivationFailureCode,
} from "../../../cloudflare/src/cf-d-neon-bootstrap-egress.js";

const CONTRACT = JSON.parse(
  readFileSync(
    new URL(
      "../../../docs/architecture/V10_CLOUDFLARE_RELEASE_ACCEPTANCE_CONTRACT.json",
      import.meta.url,
    ),
    "utf8",
  ),
);
const CANDIDATE = CONTRACT.candidate;
const GENERIC_FAILURE = "CLOUDFLARE_CF_D_ORIGIN_SYNC_DERIVATION_FAILED";


test("CF-D Worker taxonomy exactly matches the release contract", () => {
  const codes = CANDIDATE.staging_origin_sync_sanitized_derivation_codes;
  assert.ok(Array.isArray(codes));
  assert.ok(codes.length > 0);
  assert.equal(new Set(codes).size, codes.length);
  assert.deepEqual(
    new Set(CF_D_SANITIZED_DERIVATION_FAILURE_CODES),
    new Set(codes),
  );

  for (const code of codes) {
    assert.equal(typeof code, "string");
    assert.equal(sanitizedCfDDerivationFailureCode(new Error(code)), code);
  }
});

test("CF-D Worker keeps uncontracted exception text behind the generic class", () => {
  assert.equal(
    sanitizedCfDDerivationFailureCode(new Error("UNTRUSTED_INTERNAL_DETAIL")),
    GENERIC_FAILURE,
  );
  assert.equal(
    sanitizedCfDDerivationFailureCode("UNTRUSTED_INTERNAL_DETAIL"),
    GENERIC_FAILURE,
  );
});

test("CF-D retry contract contains only known custody failure classes", () => {
  const sanitizedCodes = new Set(
    CANDIDATE.staging_origin_sync_sanitized_derivation_codes,
  );
  const retryableCodes = CANDIDATE.staging_origin_sync_retryable_codes;
  assert.ok(Array.isArray(retryableCodes));
  assert.equal(new Set(retryableCodes).size, retryableCodes.length);

  const outerTransient = new Set([
    "CLOUDFLARE_CF_D_ORIGIN_SYNC_STAGING_NOT_READY",
    "CLOUDFLARE_CF_D_ORIGIN_SYNC_UNAVAILABLE",
  ]);
  for (const code of retryableCodes) {
    assert.ok(sanitizedCodes.has(code) || outerTransient.has(code));
  }
});
