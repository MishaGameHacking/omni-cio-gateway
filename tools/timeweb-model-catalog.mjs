/** Read the existing gateway catalogue; no model invocation or account change. */
import https from 'node:https';
import { writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

export const REQUESTED_MODELS = Object.freeze(['gpt-6-luna', 'gpt-6.1-sol', 'gpt-6-astra']);
const MAX_BYTES = 2 * 1024 * 1024;

export class CatalogueError extends Error {
  constructor(code) { super(code); this.code = code; }
}

function credential(value) {
  if (typeof value !== 'string' || !value || value.length > 16384 || /[^\x21-\x7e]/.test(value)) {
    throw new CatalogueError('gateway_credential_missing_or_invalid');
  }
  return value;
}

export function readGatewayCatalogue(apiKey) {
  credential(apiKey);
  // Fixed origin and GET path. No proxy, redirects, arbitrary URLs, retries,
  // completion calls, plaintext export or nonstandard TLS verification.
  return new Promise((resolve, reject) => {
    let finished = false;
    const finish = (error, result) => {
      if (finished) return;
      finished = true;
      clearTimeout(deadline);
      if (error) reject(error); else resolve(result);
    };
    const req = https.request({ hostname:'api.timeweb.ai', port:443, method:'GET', path:'/v1/models',
      headers:{ Authorization:`Bearer ${apiKey}`, Accept:'application/json', 'Accept-Encoding':'identity' },
    }, response => {
      if (response.statusCode !== 200) {
        response.resume();
        finish(new CatalogueError(`gateway_http_${response.statusCode}`));
        return;
      }
      if (!['', 'identity'].includes(String(response.headers['content-encoding'] ?? '').toLowerCase())) {
        response.destroy();
        finish(new CatalogueError('gateway_encoding_rejected'));
        return;
      }
      const chunks = [];
      let size = 0;
      response.on('data', chunk => {
        size += chunk.length;
        if (size > MAX_BYTES) {
          response.destroy();
          finish(new CatalogueError('gateway_response_too_large'));
        } else chunks.push(chunk);
      });
      response.on('error', () => finish(new CatalogueError('gateway_response_incomplete')));
      response.on('end', () => {
        try { finish(null, JSON.parse(Buffer.concat(chunks).toString('utf8'))); }
        catch { finish(new CatalogueError('gateway_response_invalid_json')); }
      });
    });
    const deadline = setTimeout(() => {
      req.destroy();
      finish(new CatalogueError('gateway_timeout'));
    }, 30000);
    req.on('error', error => {
      const codes = new Set(['ENOTFOUND', 'EAI_AGAIN', 'ETIMEDOUT', 'ECONNREFUSED', 'ECONNRESET',
        'CERT_HAS_EXPIRED', 'UNABLE_TO_VERIFY_LEAF_SIGNATURE', 'UNABLE_TO_GET_ISSUER_CERT_LOCALLY',
        'ERR_TLS_CERT_ALTNAME_INVALID']);
      const suffix = codes.has(error.code) ? `_${error.code.toLowerCase()}` : '';
      finish(new CatalogueError(`gateway_connection_failed${suffix}`));
    });
    req.end();
  });
}

export function summarizeCatalogue(payload) {
  if (!payload || typeof payload !== 'object' || !Array.isArray(payload.data) || payload.data.length > 5000) {
    throw new CatalogueError('gateway_catalogue_shape_invalid');
  }
  const identifiers = new Set();
  for (const row of payload.data) {
    if (!row || typeof row.id !== 'string' || !/^[A-Za-z0-9_./:-]{1,160}$/.test(row.id) || identifiers.has(row.id)) {
      throw new CatalogueError('gateway_model_identity_invalid');
    }
    identifiers.add(row.id);
  }
  // Only exact requested names and the documented provider prefix qualify.
  // A similarly named model or a dated variant is not silently substituted.
  return REQUESTED_MODELS.map(name => ({ requested:name,
    advertised_ids:[name, `openai/${name}`].filter(id => identifiers.has(id)) }));
}

export async function inspectCatalogue(apiKey, read = readGatewayCatalogue) {
  const report = { schema_version:1, checked_at_utc:new Date().toISOString(),
    provider:'Timeweb AI Gateway', origin:'https://api.timeweb.ai/v1',
    status:'unverified', requested_models:[], model_invocations:0, financial_orders:0,
    owner_data_transmitted:false, inference_access_verified:false, qualification_passed:false };
  try {
    credential(apiKey);
    report.requested_models = summarizeCatalogue(await read(apiKey));
    report.status = 'catalogue_received';
  } catch (error) {
    report.status = 'unavailable';
    // Never serialize upstream bodies, error messages, headers or credentials.
    report.reason = error instanceof CatalogueError ? error.code : 'gateway_probe_failed';
  }
  return report;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const report = await inspectCatalogue(process.env.TIMEWEB_AI_TOKEN ?? '');
  await writeFile('timeweb-model-catalog.json', JSON.stringify(report, null, 2)+'\n', {mode:0o600});
  console.log(JSON.stringify({status:report.status, reason:report.reason, model_invocations:0,
    report:'timeweb-model-catalog.json'}));
  process.exitCode = report.status === 'catalogue_received' ? 0 : 2;
}
