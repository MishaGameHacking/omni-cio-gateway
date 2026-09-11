import handler from './handler.mjs';

const SOURCE_BUNDLE_SHA256 = '__OMNI_CIO_CF_D_SOURCE_BUNDLE_SHA256__';
const SOURCE_PROVENANCE_PATH = '/';
const SOURCE_PROVENANCE_HEADER = 'x-omni-source-provenance';
const SOURCE_PROVENANCE_HEADER_VALUE = 'v1';

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

function isProvenanceRequest(request, url) {
  return (
    request.method === 'GET' &&
    url.pathname === SOURCE_PROVENANCE_PATH &&
    url.search === '' &&
    request.headers.get(SOURCE_PROVENANCE_HEADER) === SOURCE_PROVENANCE_HEADER_VALUE
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
  isProvenanceRequest,
};
