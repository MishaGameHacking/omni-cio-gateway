import { Container, getRandom } from "@cloudflare/containers";
import { env as runtimeEnv } from "cloudflare:workers";
import { SOURCE_SHA } from "./generated-build-info.js";

const BACKEND_INSTANCE_COUNT = 1;
const INTERNAL_HOST = "omni-cio.internal";
const INTERNAL_PROXY_URL = "https://omni-cio.internal/_omni/cloudflare-proxy";
const REQUIRED_DATABASE_SECRET = "OMNI_V10_POSTGRES_DSN";
const MAX_ROUTE_PATH_LENGTH = 4096;
const MAX_ROUTE_QUERY_LENGTH = 8192;

function backendEnvironment() {
  const databaseDsn = runtimeEnv[REQUIRED_DATABASE_SECRET];
  return {
    OMNI_V10_CLOUDFLARE_RUNTIME: "1",
    OMNI_V10_RELEASE_SHA: SOURCE_SHA,
    OMNI_V10_INTERNAL_HOSTNAME: INTERNAL_HOST,
    ...(typeof databaseDsn === "string" && databaseDsn.length > 0
      ? { OMNI_V10_POSTGRES_DSN: databaseDsn }
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
  headers.delete("x-omni-route-path");
  headers.delete("x-omni-route-query");
  if (clientIp) {
    headers.set("x-forwarded-for", clientIp);
  }
  headers.set("x-forwarded-host", INTERNAL_HOST);
  headers.set("x-forwarded-proto", "https");
  headers.set("x-omni-edge-provider", "cloudflare");
  headers.set("x-omni-source-sha", SOURCE_SHA);
  headers.set("x-omni-route-path", encodeURIComponent(routeUrl.pathname));
  headers.set("x-omni-route-query", encodeURIComponent(query));
  return new Request(INTERNAL_PROXY_URL, {
    method: request.method,
    headers,
    body: request.body,
    redirect: "manual",
  });
}

async function proxyBackend(request, env, routeUrl) {
  if (!routeIsBounded(routeUrl)) {
    return hardenedJson({ detail: "ROUTE_TOO_LARGE" }, 414);
  }
  if (
    typeof env[REQUIRED_DATABASE_SECRET] !== "string" ||
    env[REQUIRED_DATABASE_SECRET].length === 0
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
  const instance = await getRandom(env.BACKEND, BACKEND_INSTANCE_COUNT);
  return instance.fetch(backendRequest(request, routeUrl));
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
