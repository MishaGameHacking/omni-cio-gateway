import handler from './handler.mjs';

const SOURCE_BUNDLE_SHA256 = '__OMNI_CIO_CF_D_SOURCE_BUNDLE_SHA256__';
const SOURCE_PROVENANCE_PATH = '/';

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
  return request.method === 'GET' && url.pathname === SOURCE_PROVENANCE_PATH;
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
  SOURCE_BUNDLE_SHA256,
  SOURCE_PROVENANCE_PATH,
  isProvenanceRequest,
};
