/** Sign public tariff facts in CI; the cloud administration key stays in CI. */
import {createHash, createPrivateKey, sign} from 'node:crypto';
import {writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import {gatewayRequest, GatewayError, validCredential} from './timeweb-ai-http.mjs';

export const SOURCE = 'https://api.timeweb.cloud/api/v3/cloud-ai/models';
export const MODEL = 'openai/gpt-6.1-sol';
export const PURPOSE = 'AnalystAI:Timeweb:PublicPrices:v1';
const DAY = 86400;

function fail(code) { throw new GatewayError(code); }

// Convert the provider's decimal RUB/token to integer micro-RUB/million.
// BigInt and upward rounding prevent an underestimated reservation.
export function rate(value) {
  if (!['string', 'number'].includes(typeof value)) fail('price_number_invalid');
  const text = String(value);
  const match = /^(\d{1,16})(?:\.(\d{1,18}))?(?:e([+-]?\d{1,2}))?$/i.exec(text);
  if (!match) fail('price_number_invalid');
  const digits = BigInt(match[1] + (match[2] || ''));
  const exponent = 12 + Number(match[3] || 0) - (match[2]?.length || 0);
  if (Math.abs(exponent) > 30) fail('price_number_invalid');
  const divisor = exponent < 0 ? 10n ** BigInt(-exponent) : 1n;
  const micro = exponent >= 0 ? digits * 10n ** BigInt(exponent) : (digits + divisor - 1n) / divisor;
  if (micro <= 0n || micro > 10_000n * 1_000_000n) fail('price_outside_reviewed_bound');
  return micro;
}

function decimal(micro) {
  return `${micro / 1_000_000n}.${String(micro % 1_000_000n).padStart(6, '0')}`;
}

function checkTiers(tiers) {
  if (!Array.isArray(tiers) || tiers.length > 32) fail('price_tiers_unreviewed');
  let previous = -1;
  for (const tier of tiers) {
    if (!tier || typeof tier !== 'object' || Array.isArray(tier) ||
        Object.keys(tier).sort().join() !== 'above_context_tokens,cost_in,cost_out' ||
        !Number.isSafeInteger(tier.above_context_tokens) || tier.above_context_tokens <= previous ||
        tier.above_context_tokens > 2_000_000) fail('price_tiers_unreviewed');
    previous = tier.above_context_tokens;
    rate(tier.cost_in); rate(tier.cost_out);
    // The official ModelPriceTier contract applies strictly ABOVE the threshold.
    // Every request is independently capped at 16,384 total input+output tokens.
    // Applicable tiers (including their cache semantics) require another review.
    if (tier.above_context_tokens < 16384) fail('price_context_tier_requires_review');
  }
}

export function makePayload(catalogue, now = Date.now()) {
  if (!Number.isSafeInteger(now) || now < 0) fail('price_clock_invalid');
  const models = catalogue?.models;
  if (!Array.isArray(models) || models.length > 5000 || models.some(row => !row || typeof row !== 'object' || Array.isArray(row))) {
    fail('price_catalogue_invalid');
  }
  const rows = models.filter(row => row.model_name === MODEL);
  if (rows.length !== 1) fail('price_model_identity_invalid');
  const row = rows[0];
  if (row.is_stopped !== false || row.is_deprecated !== false) fail('price_model_unavailable');
  checkTiers(row.price_tiers);
  const values = row.parameter_values;
  if (!values || typeof values !== 'object' || Array.isArray(values)) fail('price_values_missing');
  if (Object.hasOwn(values, 'pricing_unit') && values.pricing_unit !== 'token') fail('price_unit_unreviewed');
  const costs = [values.cost_in, Object.hasOwn(values, 'cost_cache_write') ? values.cost_cache_write : values.cost_in].map(rate);
  const input = costs.reduce((a, b) => a > b ? a : b);
  const output = rate(values.cost_out);
  const issued = Math.floor(now / 1000);
  return {schema_version: 1, purpose: PURPOSE, source: SOURCE, model: MODEL,
    issued_at: issued, valid_until: issued + DAY,
    currency: 'RUB', unit: 'million_tokens',
    interpretation: 'raw_cost_as_rub_per_token_no_discounts',
    input_rub_per_million: decimal(input), output_rub_per_million: decimal(output),
    max_context_tokens: 16384, max_output_tokens: 1600,
    source_sha256: createHash('sha256').update(JSON.stringify(catalogue)).digest('hex')};
}

export function signPayload(payload, privatePem) {
  let key;
  try { key = createPrivateKey(privatePem); } catch { fail('price_signing_key_invalid'); }
  if (key.asymmetricKeyType !== 'ed25519') fail('price_signing_key_invalid');
  const bytes = Buffer.from(JSON.stringify(payload), 'utf8');
  if (bytes.length > 4096) fail('price_payload_too_large');
  return {schema_version: 1, payload: bytes.toString('base64'), signature: sign(null, bytes, key).toString('base64')};
}

export async function collectFeed(token, privatePem, request = gatewayRequest, now = Date.now()) {
  validCredential(token);
  const catalogue = await request('prices', token);
  return signPayload(makePayload(catalogue, now), privatePem);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const feed = await collectFeed(process.env.TIMEWEB_CLOUD_TOKEN || '', process.env.ANALYST_PRICE_SIGNING_KEY || '');
    const target = process.argv[2] || 'timeweb-price-feed.json';
    // The output is public signed metadata. Never write credentials or model responses.
    await writeFile(target, JSON.stringify(feed) + '\n', {mode: 0o600});
    console.log(JSON.stringify({status: 'signed', model: MODEL, model_invocations: 0}));
  } catch (error) {
    console.log(JSON.stringify({status: 'unavailable', reason: error instanceof GatewayError ? error.code : 'price_feed_failed'}));
    process.exitCode = 2;
  }
}
