const LOCAL_PREVIEW_PORT = 4173;
const CI_PREVIEW_PORT_BASE = 18000;
const CI_PREVIEW_PORT_SPAN = 26000;

function requireDigits(value, label) {
  if (!/^\d+$/.test(value)) {
    throw new Error(`${label} must contain only decimal digits.`);
  }
  return value;
}

function parsePort(value, label) {
  requireDigits(value, label);
  const port = Number(value);
  if (!Number.isSafeInteger(port) || port < 1024 || port > 65535) {
    throw new Error(`${label} must be an integer from 1024 through 65535.`);
  }
  return port;
}

function hashIdentity(identity) {
  let hash = 0x811c9dc5;
  for (const character of identity) {
    hash ^= character.codePointAt(0);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash;
}

export function resolvePreviewPort(env = process.env) {
  const explicit = env.OMNI_WEB_PREVIEW_PORT?.trim();
  if (explicit) return parsePort(explicit, "OMNI_WEB_PREVIEW_PORT");

  const runId = env.GITHUB_RUN_ID?.trim();
  if (!runId) return LOCAL_PREVIEW_PORT;
  requireDigits(runId, "GITHUB_RUN_ID");

  const attempt = env.GITHUB_RUN_ATTEMPT?.trim() || "1";
  requireDigits(attempt, "GITHUB_RUN_ATTEMPT");
  if (Number(attempt) < 1) {
    throw new Error("GITHUB_RUN_ATTEMPT must be at least 1.");
  }

  const job = env.GITHUB_JOB?.trim() || "job";
  const runner = env.RUNNER_NAME?.trim() || "runner";
  const identity = `${runId}:${job}:${attempt}:${runner}`;
  return CI_PREVIEW_PORT_BASE + (hashIdentity(identity) % CI_PREVIEW_PORT_SPAN);
}

export function resolvePreviewEndpoint(env = process.env) {
  const port = resolvePreviewPort(env);
  return {
    port,
    url: `http://127.0.0.1:${port}/`,
  };
}
