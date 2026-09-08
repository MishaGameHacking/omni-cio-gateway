import {
  deriveCfDNeonBootstrapOrigin,
  sanitizedCfDDerivationFailureCode,
} from "./cf-d-neon-bootstrap-egress.js";
import { hardenedJson } from "./hardened-response.js";

export const CF_D_BOOTSTRAP_ORIGIN_CUSTODY_PATH =
  "/api/internal/v10/cf-d/bootstrap-origin-custody";
export const CF_D_ORIGIN_SYNC_TOKEN_BINDING =
  "OMNI_V10_CF_D_ORIGIN_SYNC_TOKEN";

const RUNTIME_ROLE_BINDING = "OMNI_V10_POSTGRES_RUNTIME_ROLE";
const EXPECTED_STAGING_ROLE = "omni_cio_cloudflare_staging";
const SHA_PATTERN = /^[0-9a-f]{40}$/;
const SYNC_TOKEN_PATTERN = /^[0-9a-f]{64}$/;
const SYNC_TOKEN_HEADER = "x-omni-cf-d-origin-sync-token";
const EXPECTED_SHA_HEADER = "x-omni-expected-sha";

function equalFixedHex(left, right) {
  if (
    typeof left !== "string" ||
    typeof right !== "string" ||
    !SYNC_TOKEN_PATTERN.test(left) ||
    !SYNC_TOKEN_PATTERN.test(right)
  ) {
    return false;
  }
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
}

function authorizedRequest(request, bindings, expectedSourceSha) {
  if (
    request.method !== "POST" ||
    bindings?.[RUNTIME_ROLE_BINDING] !== EXPECTED_STAGING_ROLE ||
    typeof expectedSourceSha !== "string" ||
    !SHA_PATTERN.test(expectedSourceSha)
  ) {
    return false;
  }
  const requestSha = request.headers.get(EXPECTED_SHA_HEADER);
  const presentedToken = request.headers.get(SYNC_TOKEN_HEADER);
  const expectedToken = bindings?.[CF_D_ORIGIN_SYNC_TOKEN_BINDING];
  return (
    requestSha === expectedSourceSha &&
    equalFixedHex(presentedToken, expectedToken)
  );
}

export async function handleCfDBootstrapOriginCustody(
  request,
  bindings,
  expectedSourceSha,
) {
  if (bindings?.[RUNTIME_ROLE_BINDING] !== EXPECTED_STAGING_ROLE) {
    return hardenedJson({ detail: "NOT_FOUND" }, 404);
  }
  if (!authorizedRequest(request, bindings, expectedSourceSha)) {
    return hardenedJson(
      { detail: "CLOUDFLARE_CF_D_ORIGIN_SYNC_UNAUTHORIZED" },
      403,
    );
  }
  try {
    const bootstrapOrigin = await deriveCfDNeonBootstrapOrigin(bindings);
    return hardenedJson(
      {
        status: "READY",
        source_sha: expectedSourceSha,
        bootstrap_origin: bootstrapOrigin,
      },
      200,
    );
  } catch (error) {
    return hardenedJson(
      { detail: sanitizedCfDDerivationFailureCode(error) },
      502,
    );
  }
}
