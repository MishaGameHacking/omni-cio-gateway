import https from 'node:https';

const ROUTES = Object.freeze({
  prices: {host:'api.timeweb.cloud', path:'/api/v3/cloud-ai/models', method:'GET', timeout:30000},
  price_units: {host:'api.timeweb.cloud', path:'/api/v3/cloud-ai/model-parameters', method:'GET', timeout:30000},
  responses: {host:'api.timeweb.ai', path:'/v1/responses', method:'POST', timeout:120000},
});

export class GatewayError extends Error {
  constructor(code) { super(code); this.code = code; }
}

export function validCredential(value) {
  if (typeof value !== 'string' || !value || value.length > 16384 || /[^\x21-\x7e]/.test(value)) {
    throw new GatewayError('credential_missing_or_invalid');
  }
  return value;
}

/** Fixed documented endpoints, verified TLS, no redirects or automatic retries. */
export function gatewayRequest(routeName, apiKey, payload) {
  const route = ROUTES[routeName];
  if (!route) throw new GatewayError('route_not_allowed');
  validCredential(apiKey);
  const body = payload === undefined ? null : Buffer.from(JSON.stringify(payload), 'utf8');
  if ((route.method === 'POST') !== Boolean(body) || body?.length > 32768) throw new GatewayError('request_invalid');
  return new Promise((resolve, reject) => {
    let finished = false;
    let deadline;
    const finish = (error, result) => {
      if (finished) return;
      finished = true;
      clearTimeout(deadline);
      if (error) reject(error); else resolve(result);
    };
    const request = https.request({hostname:route.host, port:443, method:route.method, path:route.path,
      headers:{Authorization:`Bearer ${apiKey}`, Accept:'application/json', 'Accept-Encoding':'identity',
        ...(body ? {'Content-Type':'application/json', 'Content-Length':body.length} : {})},
    }, response => {
      if (response.statusCode !== 200) {
        response.destroy();
        finish(new GatewayError(`http_${response.statusCode}`));
        return;
      }
      if (!['', 'identity'].includes(String(response.headers['content-encoding'] ?? '').toLowerCase())) {
        response.destroy(); finish(new GatewayError('response_encoding_invalid')); return;
      }
      let size = 0;
      const chunks = [];
      response.on('data', chunk => {
        size += chunk.length;
        if (size > 2 * 1024 * 1024) { response.destroy(); finish(new GatewayError('response_too_large')); }
        else chunks.push(chunk);
      });
      response.on('error', () => finish(new GatewayError('response_incomplete')));
      response.on('aborted', () => finish(new GatewayError('response_incomplete')));
      response.on('end', () => {
        try { finish(null, JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(Buffer.concat(chunks)))); }
        catch { finish(new GatewayError('response_invalid_json')); }
      });
    });
    deadline = setTimeout(() => { request.destroy(); finish(new GatewayError('request_timeout')); }, route.timeout);
    request.on('error', error => {
      const allowed = new Set(['ENOTFOUND','EAI_AGAIN','ETIMEDOUT','ECONNREFUSED','ECONNRESET',
        'CERT_HAS_EXPIRED','UNABLE_TO_VERIFY_LEAF_SIGNATURE','UNABLE_TO_GET_ISSUER_CERT_LOCALLY','ERR_TLS_CERT_ALTNAME_INVALID']);
      finish(new GatewayError(allowed.has(error.code) ? `connection_${error.code.toLowerCase()}` : 'connection_failed'));
    });
    request.end(body);
  });
}
