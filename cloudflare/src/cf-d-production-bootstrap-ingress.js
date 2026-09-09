export const CF_D_PRODUCTION_DATABASE_BOOTSTRAP_PATH =
  "/api/internal/v10/cf-d/production-database-bootstrap";
export const CF_D_GITHUB_OIDC_HEADER = "x-omni-github-oidc";

const EXPECTED_SHA_HEADER = "x-omni-expected-sha";
const SHA_PATTERN = /^[0-9a-f]{40}$/;
const OIDC_TOKEN_PATTERN = /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/;
const MAX_OIDC_TOKEN_BYTES = 16_384;

function utf8Bytes(value) {
  return new TextEncoder().encode(value).byteLength;
}

function ingressStopped(code, status) {
  const error = new Error(code);
  error.status = status;
  return error;
}

export function prepareCfDProductionBootstrapIngress(request, expectedSourceSha) {
  const url = new URL(request.url);
  if (
    request.method !== "POST" ||
    url.pathname !== CF_D_PRODUCTION_DATABASE_BOOTSTRAP_PATH ||
    url.search ||
    typeof expectedSourceSha !== "string" ||
    !SHA_PATTERN.test(expectedSourceSha) ||
    request.headers.get(EXPECTED_SHA_HEADER) !== expectedSourceSha
  ) {
    throw ingressStopped("CLOUDFLARE_CF_D_EXPECTED_SHA_INVALID", 403);
  }

  // GitHub OIDC is application authority, not Cloudflare edge authentication.
  // Keep it out of the public Authorization channel and materialize Bearer only
  // after the request is executing inside the trusted Worker boundary.
  if (request.headers.has("authorization")) {
    throw ingressStopped("CLOUDFLARE_CF_D_OIDC_REQUIRED", 401);
  }
  const oidcToken = request.headers.get(CF_D_GITHUB_OIDC_HEADER) ?? "";
  if (
    !oidcToken ||
    utf8Bytes(oidcToken) > MAX_OIDC_TOKEN_BYTES ||
    !OIDC_TOKEN_PATTERN.test(oidcToken)
  ) {
    throw ingressStopped("CLOUDFLARE_CF_D_OIDC_REQUIRED", 401);
  }

  const headers = new Headers(request.headers);
  headers.delete(CF_D_GITHUB_OIDC_HEADER);
  headers.set("authorization", `Bearer ${oidcToken}`);
  return new Request(request.url, {
    method: "POST",
    headers,
    body: request.body,
    redirect: "manual",
    duplex: "half",
  });
}

export function cfDProductionBootstrapIngressFailure(error) {
  if (!(error instanceof Error)) {
    return { detail: "CLOUDFLARE_CF_D_OIDC_REQUIRED", status: 401 };
  }
  if (
    error.message === "CLOUDFLARE_CF_D_EXPECTED_SHA_INVALID" &&
    error.status === 403
  ) {
    return { detail: error.message, status: 403 };
  }
  return { detail: "CLOUDFLARE_CF_D_OIDC_REQUIRED", status: 401 };
}
