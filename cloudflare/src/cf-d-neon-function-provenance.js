import { deriveCfDNeonBootstrapOrigin } from "./cf-d-neon-bootstrap-egress.js";

const JSON_MEDIA_TYPE = "application/json";
const MAX_PROVENANCE_RESPONSE_BYTES = 2_048;
const SOURCE_DIGEST_PATTERN = /^[0-9a-f]{64}$/;

export const CF_D_NEON_FUNCTION_PROVENANCE_DERIVATION_FAILED =
  "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_DERIVATION_FAILED";
export const CF_D_NEON_FUNCTION_PROVENANCE_UNAVAILABLE =
  "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_UNAVAILABLE";
export const CF_D_NEON_FUNCTION_PROVENANCE_REDIRECT_REJECTED =
  "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_REDIRECT_REJECTED";
export const CF_D_NEON_FUNCTION_PROVENANCE_RESPONSE_TOO_LARGE =
  "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_RESPONSE_TOO_LARGE";
export const CF_D_NEON_FUNCTION_PROVENANCE_INVALID =
  "CLOUDFLARE_CF_D_NEON_FUNCTION_PROVENANCE_INVALID";

const SAFE_FAILURE_CODES = new Set([
  CF_D_NEON_FUNCTION_PROVENANCE_DERIVATION_FAILED,
  CF_D_NEON_FUNCTION_PROVENANCE_UNAVAILABLE,
  CF_D_NEON_FUNCTION_PROVENANCE_REDIRECT_REJECTED,
  CF_D_NEON_FUNCTION_PROVENANCE_RESPONSE_TOO_LARGE,
  CF_D_NEON_FUNCTION_PROVENANCE_INVALID,
]);

function stopped(code) {
  throw new Error(code);
}

function isJsonResponse(response) {
  const contentType = (response.headers.get("content-type") ?? "")
    .split(";", 1)[0]
    .trim()
    .toLowerCase();
  return contentType === JSON_MEDIA_TYPE;
}

async function boundedResponseText(response) {
  if (response.body === null) {
    stopped(CF_D_NEON_FUNCTION_PROVENANCE_INVALID);
  }
  const reader = response.body.getReader();
  const chunks = [];
  let totalBytes = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      if (!(value instanceof Uint8Array)) {
        stopped(CF_D_NEON_FUNCTION_PROVENANCE_INVALID);
      }
      totalBytes += value.byteLength;
      if (totalBytes > MAX_PROVENANCE_RESPONSE_BYTES) {
        try {
          await reader.cancel();
        } finally {
          stopped(CF_D_NEON_FUNCTION_PROVENANCE_RESPONSE_TOO_LARGE);
        }
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  const body = new Uint8Array(totalBytes);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(body);
  } catch {
    stopped(CF_D_NEON_FUNCTION_PROVENANCE_INVALID);
  }
}

function exactObject(value, keys) {
  if (value === null || Array.isArray(value) || typeof value !== "object") {
    return false;
  }
  const actual = Object.keys(value);
  return (
    actual.length === keys.length &&
    keys.every((key) => Object.prototype.hasOwnProperty.call(value, key))
  );
}

function provenanceDigest(status, payload) {
  if (
    status === 200 &&
    exactObject(payload, ["status", "source_sha256"]) &&
    payload.status === "READY" &&
    typeof payload.source_sha256 === "string" &&
    SOURCE_DIGEST_PATTERN.test(payload.source_sha256)
  ) {
    return payload.source_sha256;
  }
  if (
    status === 405 &&
    exactObject(payload, ["status", "code"]) &&
    payload.status === "BLOCKED" &&
    payload.code === "METHOD_NOT_ALLOWED"
  ) {
    return null;
  }
  stopped(CF_D_NEON_FUNCTION_PROVENANCE_INVALID);
}

export function sanitizedCfDNeonFunctionProvenanceFailureCode(error) {
  if (error instanceof Error && SAFE_FAILURE_CODES.has(error.message)) {
    return error.message;
  }
  return CF_D_NEON_FUNCTION_PROVENANCE_INVALID;
}

export async function fetchCfDNeonFunctionProvenance(bindings) {
  let origin;
  try {
    origin = await deriveCfDNeonBootstrapOrigin(bindings);
  } catch {
    stopped(CF_D_NEON_FUNCTION_PROVENANCE_DERIVATION_FAILED);
  }

  let response;
  try {
    response = await fetch(
      new Request(origin, {
        method: "GET",
        headers: { Accept: JSON_MEDIA_TYPE },
        redirect: "manual",
      }),
    );
  } catch {
    stopped(CF_D_NEON_FUNCTION_PROVENANCE_UNAVAILABLE);
  }

  if (response.status >= 300 && response.status < 400) {
    stopped(CF_D_NEON_FUNCTION_PROVENANCE_REDIRECT_REJECTED);
  }
  if (!isJsonResponse(response)) {
    stopped(CF_D_NEON_FUNCTION_PROVENANCE_INVALID);
  }
  const text = await boundedResponseText(response);
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    stopped(CF_D_NEON_FUNCTION_PROVENANCE_INVALID);
  }
  return provenanceDigest(response.status, payload);
}
