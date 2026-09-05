export const CF_D_NEON_BOOTSTRAP_EGRESS_HOST = "cf-d-neon-bootstrap.internal";

const RUNTIME_DSN_BINDING = "OMNI_V10_POSTGRES_DSN";
const EXPECTED_STAGING_ROLE = "omni_cio_cloudflare_staging";
const LEGACY_TARGET_HEADER = "x-omni-neon-bootstrap-target";
const SHA_PATTERN = /^[0-9a-f]{40}$/;
const BRANCH_ID_PATTERN = /^br-[a-z0-9-]{4,57}$/;
const RUNTIME_HOST_PATTERN =
  /^ep-[a-z0-9-]{4,60}(?:-pooler)?\.(c-[a-z0-9]+)\.eu-central-1\.aws\.neon\.tech$/;
const DATABASE_SQL_URL_PATTERN =
  /^https:\/\/ep-[a-z0-9-]{4,60}(?:-pooler)?\.c-[a-z0-9]+\.eu-central-1\.aws\.neon\.tech\/sql$/;
const FUNCTION_URL_PATTERN =
  /^https:\/\/br-[a-z0-9-]{4,57}-cfdprodbootstrap\.compute\.c-[a-z0-9]+\.eu-central-1\.aws\.neon\.tech\/$/;
const MAX_RUNTIME_DSN_BYTES = 8_192;
const MAX_AUTHORIZATION_BYTES = 16_384;
const MAX_REQUEST_BODY_BYTES = 4_096;
const BRANCH_LOOKUP_TIMEOUT_MS = 10_000;
const BRANCH_LOOKUP_SQL = "SELECT current_setting('neon.branch_id', true)";
const DATABASE_DESTINATION = "database";
const FUNCTION_DESTINATION = "function";

function stopped(code) {
  throw new Error(code);
}

function encodedSize(value) {
  return new TextEncoder().encode(value).length;
}

function validatedRuntimeDatabase(bindings) {
  const value = bindings?.[RUNTIME_DSN_BINDING];
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    encodedSize(value) > MAX_RUNTIME_DSN_BYTES
  ) {
    stopped("CLOUDFLARE_CF_D_RUNTIME_DATABASE_INVALID");
  }

  let databaseUrl;
  try {
    databaseUrl = new URL(value);
  } catch {
    stopped("CLOUDFLARE_CF_D_RUNTIME_DATABASE_INVALID");
  }
  const hostname = databaseUrl.hostname.toLowerCase().replace(/\.$/, "");
  const hostMatch = RUNTIME_HOST_PATTERN.exec(hostname);
  const sslMode = databaseUrl.searchParams.getAll("sslmode");
  const channelBinding = databaseUrl.searchParams.getAll("channel_binding");
  if (
    !["postgres:", "postgresql:"].includes(databaseUrl.protocol) ||
    databaseUrl.username !== EXPECTED_STAGING_ROLE ||
    databaseUrl.password.length === 0 ||
    databaseUrl.pathname.length < 2 ||
    databaseUrl.hash !== "" ||
    hostMatch === null ||
    sslMode.length !== 1 ||
    sslMode[0] !== "require" ||
    channelBinding.length > 1 ||
    (channelBinding.length === 1 && channelBinding[0] !== "require")
  ) {
    stopped("CLOUDFLARE_CF_D_RUNTIME_DATABASE_INVALID");
  }
  return {
    connectionString: value,
    hostname,
    cell: hostMatch[1],
  };
}

function validatedAuthorization(request) {
  const value = request.headers.get("authorization");
  if (
    typeof value !== "string" ||
    !value.startsWith("Bearer ") ||
    encodedSize(value) > MAX_AUTHORIZATION_BYTES
  ) {
    stopped("CLOUDFLARE_CF_D_EGRESS_REQUEST_REJECTED");
  }
  const token = value.slice(7).trim();
  if (token.length === 0 || /\s/.test(token)) {
    stopped("CLOUDFLARE_CF_D_EGRESS_REQUEST_REJECTED");
  }
  return `Bearer ${token}`;
}

async function validatedBootstrapInput(request, expectedSourceSha) {
  let virtualUrl;
  try {
    virtualUrl = new URL(request.url);
  } catch {
    stopped("CLOUDFLARE_CF_D_EGRESS_REQUEST_REJECTED");
  }
  if (
    virtualUrl.protocol !== "http:" ||
    virtualUrl.hostname !== CF_D_NEON_BOOTSTRAP_EGRESS_HOST ||
    virtualUrl.port !== "" ||
    virtualUrl.pathname !== "/" ||
    virtualUrl.search !== "" ||
    virtualUrl.hash !== "" ||
    request.method !== "POST" ||
    request.headers.has(LEGACY_TARGET_HEADER) ||
    request.headers.get("content-type") !== "application/json" ||
    typeof expectedSourceSha !== "string" ||
    !SHA_PATTERN.test(expectedSourceSha)
  ) {
    stopped("CLOUDFLARE_CF_D_EGRESS_REQUEST_REJECTED");
  }
  const authorization = validatedAuthorization(request);
  const bodyText = await request.text();
  if (encodedSize(bodyText) > MAX_REQUEST_BODY_BYTES) {
    stopped("CLOUDFLARE_CF_D_EGRESS_REQUEST_REJECTED");
  }
  let payload;
  try {
    payload = JSON.parse(bodyText);
  } catch {
    stopped("CLOUDFLARE_CF_D_EGRESS_REQUEST_REJECTED");
  }
  if (
    payload === null ||
    Array.isArray(payload) ||
    typeof payload !== "object" ||
    Object.keys(payload).length !== 1 ||
    payload.expected_sha !== expectedSourceSha
  ) {
    stopped("CLOUDFLARE_CF_D_EGRESS_REQUEST_REJECTED");
  }
  return { authorization, expectedSha: expectedSourceSha };
}

function branchLookupRequest(runtimeDatabase) {
  return new Request(`https://${runtimeDatabase.hostname}/sql`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "Neon-Connection-String": runtimeDatabase.connectionString,
      "Neon-Raw-Text-Output": "true",
      "Neon-Array-Mode": "true",
    },
    body: JSON.stringify({ query: BRANCH_LOOKUP_SQL, params: [] }),
    redirect: "error",
    signal: AbortSignal.timeout(BRANCH_LOOKUP_TIMEOUT_MS),
  });
}

function destinationUrl(request, destination) {
  const value = request.url;
  const pattern =
    destination === DATABASE_DESTINATION
      ? DATABASE_SQL_URL_PATTERN
      : destination === FUNCTION_DESTINATION
        ? FUNCTION_URL_PATTERN
        : null;
  if (pattern === null || !pattern.test(value)) {
    stopped("CLOUDFLARE_CF_D_NEON_DESTINATION_REJECTED");
  }

  let url;
  try {
    url = new URL(value);
  } catch {
    stopped("CLOUDFLARE_CF_D_NEON_DESTINATION_REJECTED");
  }
  const expectedPath =
    destination === DATABASE_DESTINATION ? "/sql" : "/";
  if (
    url.protocol !== "https:" ||
    url.username !== "" ||
    url.password !== "" ||
    url.port !== "" ||
    url.pathname !== expectedPath ||
    url.search !== "" ||
    url.hash !== ""
  ) {
    stopped("CLOUDFLARE_CF_D_NEON_DESTINATION_REJECTED");
  }
  return value;
}

export async function fetchCfDTrustedNeonRequest(request, destination) {
  const safeUrl = destinationUrl(request, destination);
  const safeRequest = new Request(safeUrl, request);
  return fetch(safeRequest);
}

async function runtimeBranchId(runtimeDatabase) {
  let response;
  try {
    response = await fetchCfDTrustedNeonRequest(
      branchLookupRequest(runtimeDatabase),
      DATABASE_DESTINATION,
    );
  } catch (error) {
    if (
      error instanceof Error &&
      error.message === "CLOUDFLARE_CF_D_NEON_DESTINATION_REJECTED"
    ) {
      throw error;
    }
    stopped("CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_FAILED");
  }
  if (!response.ok) {
    stopped("CLOUDFLARE_CF_D_NEON_BRANCH_LOOKUP_FAILED");
  }
  let body;
  try {
    body = await response.json();
  } catch {
    stopped("CLOUDFLARE_CF_D_NEON_BRANCH_RESPONSE_INVALID");
  }
  const rows = body?.rows;
  if (
    !Array.isArray(rows) ||
    rows.length !== 1 ||
    !Array.isArray(rows[0]) ||
    rows[0].length !== 1 ||
    typeof rows[0][0] !== "string"
  ) {
    stopped("CLOUDFLARE_CF_D_NEON_BRANCH_RESPONSE_INVALID");
  }
  const branchId = rows[0][0].trim().toLowerCase();
  if (!BRANCH_ID_PATTERN.test(branchId)) {
    stopped("CLOUDFLARE_CF_D_NEON_BRANCH_RESPONSE_INVALID");
  }
  const functionLabel = `${branchId}-cfdprodbootstrap`;
  if (functionLabel.length > 63) {
    stopped("CLOUDFLARE_CF_D_NEON_BRANCH_RESPONSE_INVALID");
  }
  return branchId;
}

function bootstrapOrigin(runtimeDatabase, branchId) {
  return `https://${branchId}-cfdprodbootstrap.compute.${runtimeDatabase.cell}.eu-central-1.aws.neon.tech/`;
}

export async function prepareCfDNeonBootstrapRequest(
  request,
  bindings,
  expectedSourceSha,
) {
  const input = await validatedBootstrapInput(request, expectedSourceSha);
  const runtimeDatabase = validatedRuntimeDatabase(bindings);
  const branchId = await runtimeBranchId(runtimeDatabase);
  const providerRequest = new Request(bootstrapOrigin(runtimeDatabase, branchId), {
    method: "POST",
    headers: {
      authorization: input.authorization,
      accept: "application/json",
      "content-type": "application/json",
    },
    body: JSON.stringify({ expected_sha: input.expectedSha }),
    redirect: "manual",
  });
  destinationUrl(providerRequest, FUNCTION_DESTINATION);
  return providerRequest;
}

export async function fetchCfDNeonBootstrap(
  request,
  bindings,
  expectedSourceSha,
) {
  const providerRequest = await prepareCfDNeonBootstrapRequest(
    request,
    bindings,
    expectedSourceSha,
  );
  return fetchCfDTrustedNeonRequest(providerRequest, FUNCTION_DESTINATION);
}
