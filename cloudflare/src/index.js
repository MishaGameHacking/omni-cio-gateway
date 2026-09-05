import { Container, ContainerProxy, getRandom } from "@cloudflare/containers";
import { env as runtimeEnv } from "cloudflare:workers";
import {
  CF_D_NEON_BOOTSTRAP_EGRESS_HOST,
  prepareCfDNeonBootstrapRequest,
} from "./cf-d-neon-bootstrap-egress.js";
import { SOURCE_SHA } from "./generated-build-info.js";

export { ContainerProxy };

const BACKEND_INSTANCE_COUNT = 1;
const INTERNAL_HOST = "omni-cio.internal";
const INTERNAL_PROXY_URL = "https://omni-cio.internal/_omni/cloudflare-proxy";
const REQUIRED_DATABASE_ENV_NAME = "OMNI_V10_POSTGRES_DSN";
const REQUIRED_DATABASE_ROLE_ENV_NAME = "OMNI_V10_POSTGRES_RUNTIME_ROLE";
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
  };
}

export class Backend extends Container {
  defaultPort = 8080;
  sleepAfter = "1m";
  envVars = backendEnvironment();
}

function hardenedJson(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
      "cross-origin-opener-policy": "same-origin",
      "referrer-policy": "no-referrer",
      "x-content-type-options": "nosniff",
    },
  });
}

async function proxyCfDNeonBootstrap(request, env) {
  let providerRequest;
  try {
    providerRequest = await prepareCfDNeonBootstrapRequest(
      request,
      env,
      SOURCE_SHA,
    );
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
  return fetch(providerRequest);
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
        public_multi_user_enabled: false,
        real_trading_enabled: false,
      });
    }
    if (url.pathname === "/healthz" || url.pathname.startsWith("/api/")) {
      return proxyBackend(request, env, url);
    }
    return env.ASSETS.fetch(request);
  },
};