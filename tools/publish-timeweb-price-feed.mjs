/** Publish only a signature-verified public quote to one fixed repository path. */
import {createPublicKey, verify} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';
import {MODEL, PURPOSE, SOURCE} from './timeweb-price-feed.mjs';

const REPO = 'MishaGameHacking/omni-cio-gateway';
const BRANCH = 'codex/timeweb-model-access-2026-11-01';
const PATH = 'runtime/timeweb-price-feed.json';

export function verifyPublication(raw, publicRaw, now = Math.floor(Date.now() / 1000)) {
  if (!Buffer.isBuffer(raw) || raw.length > 8192 || !Buffer.isBuffer(publicRaw) || publicRaw.length !== 32) throw new Error('publication_invalid');
  const envelope = JSON.parse(raw.toString('utf8'));
  if (Object.keys(envelope).sort().join() !== 'payload,schema_version,signature' || envelope.schema_version !== 1) throw new Error('publication_invalid');
  const bytes = Buffer.from(envelope.payload, 'base64');
  const signature = Buffer.from(envelope.signature, 'base64');
  if (bytes.toString('base64') !== envelope.payload || signature.toString('base64') !== envelope.signature || bytes.length > 4096) throw new Error('publication_invalid');
  const key = createPublicKey({key: {kty: 'OKP', crv: 'Ed25519', x: publicRaw.toString('base64url')}, format: 'jwk'});
  if (!verify(null, bytes, key, signature)) throw new Error('publication_signature_invalid');
  const quote = JSON.parse(bytes.toString('utf8'));
  if (quote.model !== MODEL || quote.purpose !== PURPOSE || quote.source !== SOURCE ||
      !Number.isSafeInteger(quote.issued_at) || !Number.isSafeInteger(quote.valid_until) ||
      quote.issued_at > now || now - quote.issued_at > 300 || quote.valid_until !== quote.issued_at + 86400) {
    throw new Error('publication_quote_invalid');
  }
  return quote;
}

function api(args, input) {
  const executable = process.platform === 'win32' ? 'C:/Program Files/GitHub CLI/gh.exe' : 'gh';
  const result = spawnSync(executable, ['api', ...args], {input, encoding: 'utf8', timeout: 20000,
    maxBuffer: 32768, windowsHide: true, env: process.env});
  if (result.error || result.status !== 0) {
    if (!result.error && result.status !== 0 && /HTTP 404/.test(result.stderr)) return null;
    throw new Error('publication_github_failed');
  }
  return JSON.parse(result.stdout);
}

export async function publish(request = api) {
  const raw = await readFile('timeweb-price-feed.json');
  const signer = JSON.parse(await readFile('tools/fixtures/timeweb-price-signer.json', 'utf8'));
  verifyPublication(raw, Buffer.from(signer.public_key_base64, 'base64'));
  const existing = request([`repos/${REPO}/contents/${PATH}?ref=${encodeURIComponent(BRANCH)}`]);
  if (existing && (existing.type !== 'file' || !/^[0-9a-f]{40}$/.test(existing.sha))) throw new Error('publication_target_invalid');
  const body = {message: 'Refresh signed public Timeweb AI tariffs', branch: BRANCH, content: raw.toString('base64'),
    ...(existing ? {sha: existing.sha} : {})};
  const written = request(['--method', 'PUT', `repos/${REPO}/contents/${PATH}`, '--input', '-'], JSON.stringify(body));
  if (!/^[0-9a-f]{40}$/.test(written?.commit?.sha || '')) throw new Error('publication_result_unknown');
  return {status: 'published', commit: written.commit.sha, model_invocations: 0};
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try { console.log(JSON.stringify(await publish())); }
  catch { console.log(JSON.stringify({status: 'unavailable', reason: 'public_price_publication_failed'})); process.exitCode = 2; }
}
