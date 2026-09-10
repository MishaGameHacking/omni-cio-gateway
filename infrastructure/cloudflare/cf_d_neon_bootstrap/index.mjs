import { createHmac, webcrypto } from 'node:crypto';

const { subtle } = webcrypto;

const GITHUB_ISSUER = 'https://token.actions.githubusercontent.com';
const GITHUB_JWKS_URL = `${GITHUB_ISSUER}/.well-known/jwks`;
const EXPECTED_AUDIENCE = 'omni-cio-cf-d-production-database-bootstrap';
const EXPECTED_REPOSITORY = 'MishaGameHacking/omni-cio-gateway';
const EXPECTED_OWNER = 'MishaGameHacking';
const EXPECTED_REF = 'refs/heads/main';
const EXPECTED_WORKFLOW = 'V10 Cloudflare Production Release';
const EXPECTED_WORKFLOW_REF = `${EXPECTED_REPOSITORY}/.github/workflows/v10-cloudflare-production-release.yml@${EXPECTED_REF}`;
const EXPECTED_ROLE = 'omni_cio_cloudflare_prod';
const EXPECTED_DATABASE_SCHEMA = 'omni_cio_v10';
const EXPECTED_NEON_SUFFIX = '.eu-central-1.aws.neon.tech';
const DIRECT_OIDC_HEADER = 'x-omni-github-oidc';
const OIDC_CLOCK_SKEW_SECONDS = 30;
const MAX_TOKEN_BYTES = 16_384;
const MAX_REQUEST_BYTES = 4_096;
const JWKS_CACHE_MS = 5 * 60 * 1000;
const RUNTIME_CREDENTIAL_DERIVATION_DOMAIN = 'omni-cio-v10/cloudflare-production/runtime-password/v1';

let jwksCache = null;
let jwksExpiresAt = 0;

function jsonResponse(status, payload) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff',
    },
  });
}

function fail(code, status = 403) {
  return jsonResponse(status, { status: 'BLOCKED', code });
}

function decodeBase64Url(value) {
  if (typeof value !== 'string' || value.length === 0 || !/^[A-Za-z0-9_-]+$/.test(value)) {
    throw new Error('OIDC_SEGMENT_INVALID');
  }
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
  return Buffer.from(padded, 'base64');
}

function parseJsonSegment(value, code) {
  let parsed;
  try {
    parsed = JSON.parse(decodeBase64Url(value).toString('utf8'));
  } catch {
    throw new Error(code);
  }
  if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error(code);
  }
  return parsed;
}

function audienceContains(value, expected) {
  if (typeof value === 'string') return value === expected;
  if (Array.isArray(value)) return value.length > 0 && value.every((item) => typeof item === 'string') && value.includes(expected);
  return false;
}

function decimalClaim(value) {
  if (typeof value === 'number' && Number.isSafeInteger(value) && value >= 0) return String(value);
  if (typeof value === 'string' && /^[0-9]+$/.test(value)) return value;
  return null;
}

function validateClaims(claims, expectedSha, nowSeconds = Math.floor(Date.now() / 1000)) {
  const exp = Number(claims.exp);
  const nbf = Number(claims.nbf);
  const iat = Number(claims.iat);
  if (!Number.isFinite(exp) || !Number.isFinite(nbf) || !Number.isFinite(iat)) {
    throw new Error('OIDC_TIME_CLAIMS_INVALID');
  }
  if (exp <= nowSeconds - OIDC_CLOCK_SKEW_SECONDS) throw new Error('OIDC_EXPIRED');
  if (nbf > nowSeconds + OIDC_CLOCK_SKEW_SECONDS) throw new Error('OIDC_NOT_YET_VALID');
  if (iat > nowSeconds + OIDC_CLOCK_SKEW_SECONDS || iat < nowSeconds - 900) {
    throw new Error('OIDC_ISSUED_AT_INVALID');
  }
  if (claims.iss !== GITHUB_ISSUER) throw new Error('OIDC_ISSUER_INVALID');
  if (!audienceContains(claims.aud, EXPECTED_AUDIENCE)) throw new Error('OIDC_AUDIENCE_INVALID');
  if (claims.repository !== EXPECTED_REPOSITORY) throw new Error('OIDC_REPOSITORY_INVALID');
  if (claims.repository_owner !== EXPECTED_OWNER) throw new Error('OIDC_OWNER_INVALID');
  if (claims.repository_visibility !== 'private') throw new Error('OIDC_REPOSITORY_VISIBILITY_INVALID');
  if (claims.ref !== EXPECTED_REF || claims.ref_type !== 'branch') throw new Error('OIDC_REF_INVALID');
  if (claims.workflow !== EXPECTED_WORKFLOW) throw new Error('OIDC_WORKFLOW_INVALID');
  if (claims.workflow_ref !== EXPECTED_WORKFLOW_REF) throw new Error('OIDC_WORKFLOW_REF_INVALID');
  if (claims.workflow_sha !== expectedSha) throw new Error('OIDC_WORKFLOW_SHA_INVALID');
  if (claims.sha !== expectedSha) throw new Error('OIDC_SOURCE_SHA_INVALID');
  if (!['workflow_run', 'workflow_dispatch'].includes(claims.event_name)) throw new Error('OIDC_EVENT_INVALID');
  if (claims.runner_environment !== 'self-hosted') throw new Error('OIDC_RUNNER_INVALID');
  if (decimalClaim(claims.run_id) === null) throw new Error('OIDC_RUN_ID_INVALID');
  if (decimalClaim(claims.run_attempt) === null) throw new Error('OIDC_RUN_ATTEMPT_INVALID');
  if (typeof claims.jti !== 'string' || claims.jti.length < 8 || claims.jti.length > 256) throw new Error('OIDC_JTI_INVALID');
}

async function loadJwks(forceRefresh = false) {
  const now = Date.now();
  if (!forceRefresh && jwksCache !== null && now < jwksExpiresAt) return jwksCache;
  const response = await fetch(GITHUB_JWKS_URL, {
    method: 'GET',
    headers: { accept: 'application/json' },
    redirect: 'error',
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) throw new Error('OIDC_JWKS_UNAVAILABLE');
  const body = await response.json();
  if (body === null || !Array.isArray(body.keys) || body.keys.length === 0 || body.keys.length > 32) {
    throw new Error('OIDC_JWKS_INVALID');
  }
  jwksCache = body.keys;
  jwksExpiresAt = now + JWKS_CACHE_MS;
  return jwksCache;
}

function matchingSigningKeys(keys, kid) {
  return keys.filter((key) => key && key.kid === kid && key.kty === 'RSA');
}

async function signingKeyForKid(kid) {
  let keys = await loadJwks();
  let candidates = matchingSigningKeys(keys, kid);
  if (candidates.length === 0) {
    keys = await loadJwks(true);
    candidates = matchingSigningKeys(keys, kid);
  }
  if (candidates.length !== 1) throw new Error('OIDC_SIGNING_KEY_INVALID');
  return candidates[0];
}

async function verifyOidcToken(token, expectedSha) {
  if (typeof token !== 'string' || Buffer.byteLength(token, 'utf8') > MAX_TOKEN_BYTES) {
    throw new Error('OIDC_TOKEN_INVALID');
  }
  const segments = token.split('.');
  if (segments.length !== 3) throw new Error('OIDC_TOKEN_INVALID');
  const [headerSegment, payloadSegment, signatureSegment] = segments;
  const header = parseJsonSegment(headerSegment, 'OIDC_HEADER_INVALID');
  const claims = parseJsonSegment(payloadSegment, 'OIDC_CLAIMS_INVALID');
  if (header.alg !== 'RS256' || header.typ !== 'JWT' || typeof header.kid !== 'string' || header.kid.length === 0) {
    throw new Error('OIDC_HEADER_INVALID');
  }
  const signingKey = await signingKeyForKid(header.kid);
  const key = await subtle.importKey(
    'jwk',
    signingKey,
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false,
    ['verify'],
  );
  const verified = await subtle.verify(
    'RSASSA-PKCS1-v1_5',
    key,
    decodeBase64Url(signatureSegment),
    Buffer.from(`${headerSegment}.${payloadSegment}`, 'utf8'),
  );
  if (!verified) throw new Error('OIDC_SIGNATURE_INVALID');
  validateClaims(claims, expectedSha);
  return claims;
}

function connectionMetadata(connectionString) {
  let url;
  try {
    url = new URL(connectionString);
  } catch {
    throw new Error('DATABASE_URL_INVALID');
  }
  if (!['postgres:', 'postgresql:'].includes(url.protocol) || !url.username || !url.password || !url.hostname || url.pathname.length < 2) {
    throw new Error('DATABASE_URL_INVALID');
  }
  const hostname = url.hostname.toLowerCase().replace(/\.$/, '');
  if (!hostname.endsWith(EXPECTED_NEON_SUFFIX)) throw new Error('DATABASE_REGION_INVALID');
  return { url, hostname };
}

function deriveRuntimePassword(connectionString) {
  const { url } = connectionMetadata(connectionString);
  let ownerPassword;
  try {
    ownerPassword = decodeURIComponent(url.password);
  } catch {
    throw new Error('DATABASE_URL_INVALID');
  }
  if (ownerPassword.length < 16) throw new Error('DATABASE_OWNER_CREDENTIAL_INVALID');
  return createHmac('sha384', Buffer.from(ownerPassword, 'utf8'))
    .update(RUNTIME_CREDENTIAL_DERIVATION_DOMAIN, 'utf8')
    .digest('base64url');
}

async function neonQuery(connectionString, query, params = []) {
  const { hostname } = connectionMetadata(connectionString);
  const response = await fetch(`https://${hostname}/sql`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'Neon-Connection-String': connectionString,
      'Neon-Raw-Text-Output': 'true',
      'Neon-Array-Mode': 'true',
    },
    body: JSON.stringify({ query, params }),
    redirect: 'error',
    signal: AbortSignal.timeout(15_000),
  });
  if (!response.ok) throw new Error('DATABASE_QUERY_FAILED');
  const body = await response.json();
  if (body === null || typeof body !== 'object' || !Array.isArray(body.rows)) {
    throw new Error('DATABASE_QUERY_RESPONSE_INVALID');
  }
  return body;
}

async function neonTransaction(connectionString, queries) {
  const { hostname } = connectionMetadata(connectionString);
  const response = await fetch(`https://${hostname}/sql`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'Neon-Connection-String': connectionString,
      'Neon-Raw-Text-Output': 'true',
      'Neon-Array-Mode': 'true',
      'Neon-Batch-Isolation-Level': 'Serializable',
    },
    body: JSON.stringify({ queries }),
    redirect: 'error',
    signal: AbortSignal.timeout(20_000),
  });
  if (!response.ok) throw new Error('DATABASE_TRANSACTION_FAILED');
  const body = await response.json();
  if (body === null || typeof body !== 'object' || !Array.isArray(body.results) || body.results.length !== queries.length) {
    throw new Error('DATABASE_TRANSACTION_RESPONSE_INVALID');
  }
  return body.results;
}

const ROLE_CONVERGENCE_SQL = String.raw`
DO $omni_cf_d$
DECLARE
    runtime_role pg_catalog.pg_roles%ROWTYPE;
    runtime_password text;
BEGIN
    runtime_password := current_setting('omni_cio_v10.cf_d_runtime_password', true);
    IF runtime_password IS NULL OR length(runtime_password) < 48 THEN
        RAISE EXCEPTION 'CLOUDFLARE_RUNTIME_PASSWORD_INVALID' USING ERRCODE = '22023';
    END IF;

    SELECT * INTO runtime_role
    FROM pg_catalog.pg_roles
    WHERE rolname = 'omni_cio_cloudflare_prod';

    IF FOUND THEN
        IF
            NOT runtime_role.rolcanlogin OR
            runtime_role.rolsuper OR
            runtime_role.rolcreatedb OR
            runtime_role.rolcreaterole OR
            runtime_role.rolreplication OR
            runtime_role.rolbypassrls
        THEN
            RAISE EXCEPTION 'CLOUDFLARE_RUNTIME_ROLE_ATTRIBUTE_DRIFT' USING ERRCODE = '42501';
        END IF;
        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_auth_members membership
            WHERE membership.member = runtime_role.oid
        ) THEN
            RAISE EXCEPTION 'CLOUDFLARE_RUNTIME_ROLE_MEMBERSHIP_PRESENT' USING ERRCODE = '42501';
        END IF;
        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_database database_record
            WHERE database_record.datname = pg_catalog.current_database()
              AND database_record.datdba = runtime_role.oid
        ) THEN
            RAISE EXCEPTION 'CLOUDFLARE_RUNTIME_DATABASE_OWNERSHIP_FORBIDDEN' USING ERRCODE = '42501';
        END IF;
        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_namespace schema_record
            WHERE schema_record.nspname = 'omni_cio_v10'
              AND schema_record.nspowner = runtime_role.oid
        ) THEN
            RAISE EXCEPTION 'CLOUDFLARE_RUNTIME_SCHEMA_OWNERSHIP_FORBIDDEN' USING ERRCODE = '42501';
        END IF;
        IF EXISTS (
            SELECT 1
            FROM pg_catalog.pg_class relation_record
            JOIN pg_catalog.pg_namespace schema_record
              ON schema_record.oid = relation_record.relnamespace
            WHERE schema_record.nspname = 'omni_cio_v10'
              AND relation_record.relowner = runtime_role.oid
        ) OR EXISTS (
            SELECT 1
            FROM pg_catalog.pg_proc function_record
            JOIN pg_catalog.pg_namespace schema_record
              ON schema_record.oid = function_record.pronamespace
            WHERE schema_record.nspname = 'omni_cio_v10'
              AND function_record.proowner = runtime_role.oid
        ) THEN
            RAISE EXCEPTION 'CLOUDFLARE_RUNTIME_OBJECT_OWNERSHIP_FORBIDDEN' USING ERRCODE = '42501';
        END IF;
        EXECUTE pg_catalog.format(
            'ALTER ROLE %I WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
            'omni_cio_cloudflare_prod',
            runtime_password
        );
    ELSE
        EXECUTE pg_catalog.format(
            'CREATE ROLE %I WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
            'omni_cio_cloudflare_prod',
            runtime_password
        );
    END IF;
END;
$omni_cf_d$;
`;

const RUNTIME_GRANT_QUERIES = [
  `DO $database_privileges$ BEGIN EXECUTE pg_catalog.format('REVOKE CREATE, TEMPORARY ON DATABASE %I FROM PUBLIC', pg_catalog.current_database()); EXECUTE pg_catalog.format('REVOKE ALL PRIVILEGES ON DATABASE %I FROM %I', pg_catalog.current_database(), '${EXPECTED_ROLE}'); EXECUTE pg_catalog.format('GRANT CONNECT ON DATABASE %I TO %I', pg_catalog.current_database(), '${EXPECTED_ROLE}'); END; $database_privileges$;`,
  'REVOKE CREATE ON SCHEMA public FROM PUBLIC',
  `REVOKE ALL ON SCHEMA ${EXPECTED_DATABASE_SCHEMA} FROM PUBLIC`,
  `REVOKE ALL ON ALL TABLES IN SCHEMA ${EXPECTED_DATABASE_SCHEMA} FROM PUBLIC`,
  `REVOKE ALL ON ALL SEQUENCES IN SCHEMA ${EXPECTED_DATABASE_SCHEMA} FROM PUBLIC`,
  `REVOKE ALL ON ALL FUNCTIONS IN SCHEMA ${EXPECTED_DATABASE_SCHEMA} FROM PUBLIC`,
  `REVOKE ALL ON SCHEMA ${EXPECTED_DATABASE_SCHEMA} FROM ${EXPECTED_ROLE}`,
  `REVOKE ALL ON ALL TABLES IN SCHEMA ${EXPECTED_DATABASE_SCHEMA} FROM ${EXPECTED_ROLE}`,
  `REVOKE ALL ON ALL SEQUENCES IN SCHEMA ${EXPECTED_DATABASE_SCHEMA} FROM ${EXPECTED_ROLE}`,
  `REVOKE ALL ON ALL FUNCTIONS IN SCHEMA ${EXPECTED_DATABASE_SCHEMA} FROM ${EXPECTED_ROLE}`,
  `GRANT USAGE ON SCHEMA ${EXPECTED_DATABASE_SCHEMA} TO ${EXPECTED_ROLE}`,
  `GRANT EXECUTE ON FUNCTION ${EXPECTED_DATABASE_SCHEMA}.current_tenant_scope() TO ${EXPECTED_ROLE}`,
  `GRANT INSERT ON TABLE ${EXPECTED_DATABASE_SCHEMA}.tenants TO ${EXPECTED_ROLE}`,
  `GRANT SELECT, INSERT ON TABLE ${EXPECTED_DATABASE_SCHEMA}.users TO ${EXPECTED_ROLE}`,
  `GRANT SELECT, INSERT ON TABLE ${EXPECTED_DATABASE_SCHEMA}.external_identity_bindings TO ${EXPECTED_ROLE}`,
  `GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE ${EXPECTED_DATABASE_SCHEMA}.web_sessions TO ${EXPECTED_ROLE}`,
  `GRANT SELECT, INSERT, DELETE ON TABLE ${EXPECTED_DATABASE_SCHEMA}.provider_auth_transactions TO ${EXPECTED_ROLE}`,
  `GRANT SELECT, INSERT ON TABLE ${EXPECTED_DATABASE_SCHEMA}.broker_accounts TO ${EXPECTED_ROLE}`,
  `GRANT SELECT, INSERT, UPDATE ON TABLE ${EXPECTED_DATABASE_SCHEMA}.broker_connections TO ${EXPECTED_ROLE}`,
  `GRANT SELECT, INSERT ON TABLE ${EXPECTED_DATABASE_SCHEMA}.broker_connection_accounts TO ${EXPECTED_ROLE}`,
  `ALTER TABLE ${EXPECTED_DATABASE_SCHEMA}.broker_accounts ENABLE ROW LEVEL SECURITY`,
  `ALTER TABLE ${EXPECTED_DATABASE_SCHEMA}.broker_accounts FORCE ROW LEVEL SECURITY`,
  `ALTER TABLE ${EXPECTED_DATABASE_SCHEMA}.broker_connections ENABLE ROW LEVEL SECURITY`,
  `ALTER TABLE ${EXPECTED_DATABASE_SCHEMA}.broker_connections FORCE ROW LEVEL SECURITY`,
  `ALTER TABLE ${EXPECTED_DATABASE_SCHEMA}.broker_connection_accounts ENABLE ROW LEVEL SECURITY`,
  `ALTER TABLE ${EXPECTED_DATABASE_SCHEMA}.broker_connection_accounts FORCE ROW LEVEL SECURITY`,
];

async function convergeProductionRuntime(expectedSha) {
  const adminDirect = process.env.DATABASE_URL_UNPOOLED;
  const adminPooled = process.env.DATABASE_URL;
  if (!adminDirect || !adminPooled) throw new Error('DATABASE_URL_REQUIRED');

  const version = await neonQuery(adminDirect, 'SHOW server_version_num');
  const versionNum = version.rows.length === 1 ? Number.parseInt(version.rows[0][0], 10) : Number.NaN;
  if (!Number.isInteger(versionNum) || Math.floor(versionNum / 10000) !== 18) {
    throw new Error('NEON_POSTGRES18_REQUIRED');
  }

  const runtimePassword = deriveRuntimePassword(adminDirect);
  const queries = [
    { query: 'SELECT pg_advisory_xact_lock($1)', params: [132013] },
    { query: "SELECT set_config('omni_cio_v10.cf_d_runtime_password', $1, true)", params: [runtimePassword] },
    { query: ROLE_CONVERGENCE_SQL, params: [] },
    ...RUNTIME_GRANT_QUERIES.map((query) => ({ query, params: [] })),
  ];
  await neonTransaction(adminDirect, queries);

  const { url: runtimeUrl } = connectionMetadata(adminPooled);
  runtimeUrl.username = EXPECTED_ROLE;
  runtimeUrl.password = runtimePassword;
  const runtimeDsn = runtimeUrl.toString();

  const probe = await neonQuery(
    runtimeDsn,
    "SELECT current_user, current_setting('server_version_num'), " +
      "(SELECT count(*) FROM pg_catalog.pg_auth_members m JOIN pg_catalog.pg_roles r ON r.oid = m.member WHERE r.rolname = current_user), " +
      "(SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'omni_cio_v10' AND c.relname = ANY(ARRAY['broker_accounts','broker_connection_accounts','broker_connections']) AND c.relrowsecurity AND c.relforcerowsecurity)",
  );
  if (probe.rows.length !== 1) throw new Error('RUNTIME_PROBE_INVALID');
  const [role, serverVersion, memberships, forceRlsCount] = probe.rows[0];
  if (role !== EXPECTED_ROLE || Math.floor(Number.parseInt(serverVersion, 10) / 10000) !== 18 || Number.parseInt(memberships, 10) !== 0 || Number.parseInt(forceRlsCount, 10) !== 3) {
    throw new Error('RUNTIME_PROBE_FAILED');
  }

  return {
    status: 'READY',
    runtime_role: EXPECTED_ROLE,
    runtime_dsn: runtimeDsn,
    source_sha: expectedSha,
  };
}

async function readRequestJson(request) {
  const contentLength = Number(request.headers.get('content-length') || '0');
  if (Number.isFinite(contentLength) && contentLength > MAX_REQUEST_BYTES) throw new Error('REQUEST_TOO_LARGE');
  const text = await request.text();
  if (Buffer.byteLength(text, 'utf8') > MAX_REQUEST_BYTES) throw new Error('REQUEST_TOO_LARGE');
  let body;
  try {
    body = JSON.parse(text || '{}');
  } catch {
    throw new Error('REQUEST_INVALID');
  }
  if (body === null || Array.isArray(body) || typeof body !== 'object') throw new Error('REQUEST_INVALID');
  return body;
}

function oidcTokenFromRequest(request) {
  const directToken = request.headers.get(DIRECT_OIDC_HEADER);
  const authorization = request.headers.get('authorization') || '';
  if (directToken !== null && authorization !== '') {
    return { error: 'OIDC_HEADER_INVALID', token: '' };
  }
  if (directToken !== null) {
    const token = directToken.trim();
    if (token.length === 0 || /\s/.test(token)) {
      return { error: 'OIDC_TOKEN_INVALID', token: '' };
    }
    return { error: null, token };
  }
  if (!authorization.startsWith('Bearer ')) {
    return { error: 'OIDC_REQUIRED', token: '' };
  }
  const token = authorization.slice(7).trim();
  if (token.length === 0 || /\s/.test(token)) {
    return { error: 'OIDC_TOKEN_INVALID', token: '' };
  }
  return { error: null, token };
}

export default {
  async fetch(request) {
    if (request.method !== 'POST') return fail('METHOD_NOT_ALLOWED', 405);
    const ingress = oidcTokenFromRequest(request);
    if (ingress.error === 'OIDC_REQUIRED') return fail('OIDC_REQUIRED', 401);
    if (ingress.error !== null) return fail(ingress.error, 403);
    const token = ingress.token;

    let body;
    try {
      body = await readRequestJson(request);
    } catch (error) {
      return fail(error instanceof Error ? error.message : 'REQUEST_INVALID', 400);
    }
    const expectedSha = typeof body.expected_sha === 'string' ? body.expected_sha.trim().toLowerCase() : '';
    if (!/^[0-9a-f]{40}$/.test(expectedSha)) return fail('EXPECTED_SHA_INVALID', 400);

    try {
      await verifyOidcToken(token, expectedSha);
      const result = await convergeProductionRuntime(expectedSha);
      return jsonResponse(200, result);
    } catch (error) {
      const code = error instanceof Error && /^[A-Z0-9_]{3,80}$/.test(error.message) ? error.message : 'BOOTSTRAP_FAILED';
      return fail(code, code.startsWith('OIDC_') ? 403 : 502);
    }
  },
};

export {
  DIRECT_OIDC_HEADER,
  EXPECTED_AUDIENCE,
  EXPECTED_REPOSITORY,
  EXPECTED_ROLE,
  EXPECTED_WORKFLOW_REF,
  audienceContains,
  connectionMetadata,
  decimalClaim,
  deriveRuntimePassword,
  oidcTokenFromRequest,
  validateClaims,
};
