export const CF_D_NEON_BOOTSTRAP_EGRESS_HOST = "cf-d-neon-bootstrap.internal";
export const CF_D_NEON_BOOTSTRAP_TARGET_HEADER = "x-omni-neon-bootstrap-target";

const CF_D_NEON_BOOTSTRAP_HOST_PATTERN =
  /^br-[a-z0-9-]{4,57}-cfdprodbootstrap\.compute\.c-[a-z0-9]+\.eu-central-1\.aws\.neon\.tech$/;
const MAX_CF_D_NEON_TARGET_BYTES = 512;

function stopped(code) {
  throw new Error(code);
}

export function validatedCfDNeonBootstrapTarget(value) {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    new TextEncoder().encode(value).length > MAX_CF_D_NEON_TARGET_BYTES
  ) {
    stopped("CLOUDFLARE_CF_D_NEON_TARGET_INVALID");
  }

  let target;
  try {
    target = new URL(value);
  } catch {
    stopped("CLOUDFLARE_CF_D_NEON_TARGET_INVALID");
  }

  const hostname = target.hostname.toLowerCase();
  if (
    target.protocol !== "https:" ||
    target.username !== "" ||
    target.password !== "" ||
    target.port !== "" ||
    target.pathname !== "/" ||
    target.search !== "" ||
    target.hash !== "" ||
    !CF_D_NEON_BOOTSTRAP_HOST_PATTERN.test(hostname)
  ) {
    stopped("CLOUDFLARE_CF_D_NEON_TARGET_INVALID");
  }
  return `https://${hostname}/`;
}

export function prepareCfDNeonBootstrapRequest(request) {
  const virtualUrl = new URL(request.url);
  if (
    virtualUrl.protocol !== "http:" ||
    virtualUrl.hostname !== CF_D_NEON_BOOTSTRAP_EGRESS_HOST ||
    virtualUrl.port !== "" ||
    virtualUrl.pathname !== "/" ||
    virtualUrl.search !== "" ||
    virtualUrl.hash !== "" ||
    request.method !== "POST"
  ) {
    stopped("CLOUDFLARE_CF_D_EGRESS_REQUEST_REJECTED");
  }

  const targetUrl = validatedCfDNeonBootstrapTarget(
    request.headers.get(CF_D_NEON_BOOTSTRAP_TARGET_HEADER),
  );
  const headers = new Headers(request.headers);
  headers.delete(CF_D_NEON_BOOTSTRAP_TARGET_HEADER);
  headers.delete("host");

  return new Request(targetUrl, {
    method: "POST",
    headers,
    body: request.body,
    redirect: "manual",
    duplex: "half",
  });
}
