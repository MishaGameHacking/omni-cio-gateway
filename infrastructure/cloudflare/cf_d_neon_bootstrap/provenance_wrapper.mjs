import handler from './handler.mjs';

const SOURCE_BUNDLE_SHA256 = '__OMNI_CIO_CF_D_SOURCE_BUNDLE_SHA256__';
const SOURCE_PROVENANCE_PATH = '/';
const SOURCE_PROVENANCE_QUERY = '?omni_source_provenance=v1';
const SOURCE_PROVENANCE_HEADER = 'x-omni-source-provenance';
const SOURCE_PROVENANCE_HEADER_VALUE = 'v1';
const SOURCE_PROVENANCE_USER_AGENT = 'omni-cio-v10-cf-d-neon-function-deploy/2';

function provenanceResponse() {
  return new Response(
    JSON.stringify({ status: 'READY', source_sha256: SOURCE_BUNDLE_SHA256 }),
    {
      status: 200,
      headers: {
        'content-type': 'application/json; charset=utf-8',
        'cache-control': 'no-store',
        'x-content-type-options': 'nosniff',
      },
    },
  );
}

function hasHeaderProvenanceDiscriminator(request) {
  return (
    request.headers.get(SOURCE_PROVENANCE_HEADER) === SOURCE_PROVENANCE_HEADER_VALUE ||
    request.headers.get('user-agent') === SOURCE_PROVENANCE_USER_AGENT
  );
}

function hasProvenanceDiscriminator(request, url) {
  return (
    url.search === SOURCE_PROVENANCE_QUERY ||
    (url.search === '' && hasHeaderProvenanceDiscriminator(request))
  );
}

function isProvenanceRequest(request, url) {
  return (
    request.method === 'GET' &&
    url.pathname === SOURCE_PROVENANCE_PATH &&
    hasProvenanceDiscriminator(request, url)
  );
}

export default {
  fetch(request) {
    const url = new URL(request.url);
    if (isProvenanceRequest(request, url)) {
      return provenanceResponse();
    }
    return handler.fetch(request);
  },
};

export {
  SOURCE_PROVENANCE_HEADER,
  SOURCE_PROVENANCE_HEADER_VALUE,
  SOURCE_PROVENANCE_PATH,
  SOURCE_PROVENANCE_QUERY,
  SOURCE_PROVENANCE_USER_AGENT,
  hasHeaderProvenanceDiscriminator,
  hasProvenanceDiscriminator,
  isProvenanceRequest,
};
