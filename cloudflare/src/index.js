import { Container, getRandom } from "@cloudflare/containers";
import { env as runtimeEnv } from "cloudflare:workers";
import {
  CF_D_BOOTSTRAP_ORIGIN_CUSTODY_PATH,
  handleCfDBootstrapOriginCustody,
} from "./cf-d-bootstrap-origin-custody.js";
import {
  CF_D_NEON_BOOTSTRAP_EGRESS_HOST,
  fetchCfDNeonBootstrap,
} from "./cf-d-neon-bootstrap-egress.js";
import {
  CF_D_GITHUB_OIDC_HEADER,
  CF_D_PRODUCTION_DATABASE_BOOTSTRAP_PATH,
  cfDProductionBootstrapIngressFailure,
  prepareCfDProductionBootstrapIngress,
} from "./cf-d-production-bootstrap-ingress.js";
import { SOURCE_SHA } from "./generated-build-info.js";
import { hardenedJson } from "./hardened-response.js";

export { ContainerProxy } from "@cloudflare/containers";

const BACKEND_INSTANCE_COUNT = 1;
const INTERNAL_HOST = "omni-cio.internal";
const INTERNAL_PROXY_URL = "https://omni-cio.internal/_omni/cloudflare-proxy";
const REQUIRED_DATABASE_ENV_NAME = "OMNI_V10_POSTGRES_DSN";
const REQUIRED_DATABASE_ROLE_ENV_NAME = "OMNI_V10_POSTGRES_RUNTIME_ROLE";
const PUBLIC_MULTI_USER_ENV_NAME = "PUBLIC_MULTI_USER_ENABLED";
const TELEGRAM_LOGIN_ENV_NAME = "OMNI_V10_TELEGRAM_LOGIN_ENABLED";
const VK_ID_LOGIN_ENV_NAME = "OMNI_V10_VK_ID_LOGIN_ENABLED";
const PRODUCTION_RUNTIME_ROLE = "omni_cio_cloudflare_prod";
const PRODUCT_AUTH_SECRET_ENV_NAMES = Object.freeze([
  "OMNI_V10_TELEGRAM_OIDC_CLIENT_ID",
  "OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET",
  "OMNI_V10_VK_ID_CLIENT_ID",
  "OMNI_V10_IDENTITY_BINDING_KEY_HEX",
  "OMNI_V10_CSRF_BINDING_KEY_HEX",
]);
const ALLOWED_DATABASE_RUNTIME_ROLES = new Set([
  "omni_cio_cloudflare_prod",
  "omni_cio_cloudflare_staging",
]);
const MAX_ROUTE_PATH_LENGTH = 4096;
const MAX_ROUTE_QUERY_LENGTH = 8192;

function runtimeDatabaseRole(bindings) {
  const value = bindings[REQUIRED_DATABASE_ROLE_ENV_NAME];
  return typeof value === "string" && ALLOWED_DATABASE_RUNTIME_ROLES.has(value)
    ? value
    : null;
}

function booleanFlagValue(bindings, name, invalidCode) {
  const value = bindings[name];
  if (value === undefined || value === null || value === "") {
    return "false";
  }
  if (value !== "true" && value !== "false") {
    throw new Error(invalidCode);
  }
  return value;
}

function publicMultiUserValue(bindings) {
  return booleanFlagValue(
    bindings,
    PUBLIC_MULTI_USER_ENV_NAME,
    "CLOUDFLARE_PUBLIC_MULTI_USER_FLAG_INVALID",
  );
}

function productAuthEnvironment(bindings, runtimeRole) {
  const result = {
    PUBLIC_MULTI_USER_ENABLED: publicMultiUserValue(bindings),
    OMNI_V10_TELEGRAM_LOGIN_ENABLED: booleanFlagValue(
      bindings,
      TELEGRAM_LOGIN_ENV_NAME,
      "CLOUDFLARE_TELEGRAM_LOGIN_FLAG_INVALID",
    ),
    OMNI_V10_VK_ID_LOGIN_ENABLED: booleanFlagValue(
      bindings,
      VK_ID_LOGIN_ENV_NAME,
      "CLOUDFLARE_VK_ID_LOGIN_FLAG_INVALID",
    ),
  };
  if (runtimeRole !== PRODUCTION_RUNTIME_ROLE) {
    return result;
  }
  for (const name of PRODUCT_AUTH_SECRET_ENV_NAMES) {
    const value = bindings[name];
    if (typeof value === "string" && value.length > 0) {
      result[name] = value;
    }
  }
  return result;
}

function backendEnvironment() {
  const databaseDsn = runtimeEnv[REQUIRED_DATABASE_ENV_NAME];
  const runtimeRole = runtimeDatabaseRole(runtimeEnv);
  return {
    OMNI_V10_CLOUDFLARE_RUNTIME: "1",
    OMNI_V10_RELEASE_SHA: SOURCE_SHA,
    OMNI_V10_INTERNAL_HOSTNAME: INTERNAL_HOST,
    ...(typeof databaseDsn === "string" && databaseDsn.length > 0
      ? { OMNI_V10_POSTGRES_DSN: databaseDsn }
      : {}),
    ...(runtimeRole
      ? { OMNI_V10_POSTGRES_RUNTIME_ROLE: runtimeRole }
      : {}),
    ...productAuthEnvironment(runtimeEnv, runtimeRole),
  };
}

export class Backend extends Container {
  defaultPort = 8080;
  sleepAfter = "1m";
  interceptHttps = true;
  envVars = backendEnvironment();
}

async function proxyCfDNeonBootstrap(request, env) {
  try {
    return await fetchCfDNeonBootstrap(request, env, SOURCE_SHA);
  } catch (error) {
    const requestRejected =
      error instanceof Error &&
      error.message === "CLOUDFLARE_CF_D_EGRESS_REQUEST_REJECTED";
    return hardenedJson(
      {
        detail: requestRejected
          ? "CLOUDFLARE_CF_D_EGRESS_REQUEST_REJECTED"
          : "CLOUDFLARE_CF_D_NEON_BOOTSTRAP_UNAVAILABLE",
      },
      requestRejected ? 403 : 502,
    );
  }
}

Backend.outboundByHost = {
  [CF_D_NEON_BOOTSTRAP_EGRESS_HOST]: proxyCfDNeonBootstrap,
};

function routeIsBounded(url) {
  const query = url.search.startsWith("?") ? url.search.slice(1) : url.search;
  return (
    url.pathname.length <= MAX_ROUTE_PATH_LENGTH &&
    query.length <= MAX_ROUTE_QUERY_LENGTH
  );
}

function backendRequest(request, routeUrl) {
  const clientIp = request.headers.get("cf-connecting-ip");
  const query = routeUrl.search.startsWith("?")
    ? routeUrl.search.slice(1)
    : routeUrl.search;
  const headers = new Headers(request.headers);
  headers.set("host", INTERNAL_HOST);
  headers.delete("forwarded");
  headers.delete("x-forwarded-for");
  headers.delete("x-forwarded-host");
  headers.delete("x-forwarded-proto");
  headers.delete("x-omni-client-ip");
  headers.delete("x-omni-route-path");
  headers.delete("x-omni-route-query");
  headers.delete("x-omni-edge-provider");
  headers.delete("x-omni-source-sha");
  headers.delete(CF_D_GITHUB_OIDC_HEADER);
  if (!clientIp) {
    throw new Error("CLOUDFLARE_CLIENT_IP_MISSING");
  }
  headers.set("x-omni-client-ip", clientIp);
  headers.set("x-omni-edge-provider", "cloudflare");
  headers.set("x-omni-source-sha", SOURCE_SHA);
  headers.set("x-omni-route-path", encodeURIComponent(routeUrl.pathname));
  headers.set("x-omni-route-query", encodeURIComponent(query));
  return new Request(INTERNAL_PROXY_URL, {
    method: request.method,
    headers,
    body: request.body,
    redirect: "manual",
    duplex: "half",
  });
}

async function proxyBackend(request, env, routeUrl) {
  if (!routeIsBounded(routeUrl)) {
    return hardenedJson({ detail: "ROUTE_TOO_LARGE" }, 414);
  }
  if (
    typeof env[REQUIRED_DATABASE_ENV_NAME] !== "string" ||
    env[REQUIRED_DATABASE_ENV_NAME].length === 0
  ) {
    return hardenedJson(
      {
        status: "unavailable",
        detail: "CLOUDFLARE_RUNTIME_DATABASE_NOT_CONFIGURED",
        release_sha: SOURCE_SHA,
      },
      503,
    );
  }
  if (!runtimeDatabaseRole(env)) {
    return hardenedJson(
      {
        status: "unavailable",
        detail: "CLOUDFLARE_RUNTIME_DATABASE_ROLE_NOT_CONFIGURED",
        release_sha: SOURCE_SHA,
      },
      503,
    );
  }
  const instance = await getRandom(env.BACKEND, BACKEND_INSTANCE_COUNT);
  try {
    return await instance.fetch(backendRequest(request, routeUrl));
  } catch (error) {
    if (error instanceof Error && error.message === "CLOUDFLARE_CLIENT_IP_MISSING") {
      return hardenedJson({ detail: "CLOUDFLARE_EDGE_IDENTITY_MISSING" }, 400);
    }
    throw error;
  }
}

async function proxyCfDProductionDatabaseBootstrap(request, env, routeUrl) {
  try {
    const trustedRequest = prepareCfDProductionBootstrapIngress(
      request,
      SOURCE_SHA,
    );
    return await proxyBackend(trustedRequest, env, routeUrl);
  } catch (error) {
    const failure = cfDProductionBootstrapIngressFailure(error);
    return hardenedJson({ detail: failure.detail }, failure.status);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/api/v10/release") {
      return hardenedJson({
        status: "ok",
        platform: "cloudflare",
        source_sha: SOURCE_SHA,
        backend: "container",
        static_assets: true,
        public_multi_user_enabled: publicMultiUserValue(env) === "true",
        real_trading_enabled: false,
      });
    }
    if (url.pathname === CF_D_BOOTSTRAP_ORIGIN_CUSTODY_PATH) {
      return handleCfDBootstrapOriginCustody(request, env, SOURCE_SHA);
    }
    if (url.pathname === CF_D_PRODUCTION_DATABASE_BOOTSTRAP_PATH) {
      return proxyCfDProductionDatabaseBootstrap(request, env, url);
    }
    if (url.pathname === "/healthz" || url.pathname.startsWith("/api/")) {
      return proxyBackend(request, env, url);
    }
    return env.ASSETS.fetch(request);
  },
};
