import {strict as assert} from 'node:assert';
import {createHash, generateKeyPairSync, verify} from 'node:crypto';
import test from 'node:test';
import {collectFeed, makePayload, MODEL, rate, signPayload} from '../timeweb-price-feed.mjs';
import {verifyPublication} from '../publish-timeweb-price-feed.mjs';

function catalogue(changes = {}) {
  return {models: [{model_name: MODEL, is_stopped: false, is_deprecated: false, price_tiers: [],
    parameter_values: {cost_in: 0.00027, cost_out: 0.00135, cost_cache_write: 0.0003375}, ...changes}]};
}

test('exact decimal upper bounds include cache write and ignore discounts', () => {
  const payload = makePayload(catalogue(), 1793540000123);
  assert.equal(payload.input_rub_per_million, '337.500000');
  assert.equal(payload.output_rub_per_million, '1350.000000');
  assert.equal(payload.valid_until - payload.issued_at, 86400);
  assert.equal(payload.source_sha256, createHash('sha256').update(JSON.stringify(catalogue())).digest('hex'));
  assert.equal(rate('0.0000000000001'), 1n);
  assert.equal(rate('3.375e-4'), 337500000n);
  assert.equal(rate('0.000337500000000001'), 337500001n);
  for (const value of [0, -1, true, null, {}, NaN, Infinity, '0.1', '1e99', '1,25', ' 0.0001', '0.0001\n']) {
    assert.throws(() => rate(value));
  }
});

test('missing, stopped, ambiguous or tiered model prices cannot become a fresh quote', () => {
  for (const changes of [{is_stopped: true}, {is_deprecated: true}, {is_stopped: undefined},
    {price_tiers: [{threshold: 10}]}, {price_tiers: {}}, {parameter_values: {cost_in: 1e-5, cost_out: 1e-4}}]) {
    assert.throws(() => makePayload(catalogue(changes)));
  }
  const duplicate = catalogue(); duplicate.models.push(duplicate.models[0]);
  assert.throws(() => makePayload(duplicate));
  assert.throws(() => makePayload({models: []}));
  assert.throws(() => makePayload(catalogue(), NaN));
});

test('a signed envelope verifies exact bytes and omits signing and admin credentials', async () => {
  const {publicKey, privateKey} = generateKeyPairSync('ed25519');
  const pem = privateKey.export({format: 'pem', type: 'pkcs8'});
  const calls = [];
  const feed = await collectFeed('synthetic-admin-key', pem, async (...args) => {
    calls.push(args); return catalogue();
  }, 1793540000000);
  assert.deepEqual(calls, [['prices', 'synthetic-admin-key']]);
  const payload = Buffer.from(feed.payload, 'base64');
  assert(verify(null, payload, publicKey, Buffer.from(feed.signature, 'base64')));
  payload[0] ^= 1;
  assert(!verify(null, payload, publicKey, Buffer.from(feed.signature, 'base64')));
  assert(!JSON.stringify(feed).includes('synthetic-admin-key'));
  assert(!JSON.stringify(feed).includes('PRIVATE KEY'));
  assert.throws(() => signPayload(makePayload(catalogue()), 'invalid-private-key'));
});

test('publisher rejects substitution and expired or future signed metadata before GitHub writes', () => {
  const {publicKey, privateKey} = generateKeyPairSync('ed25519');
  const pem = privateKey.export({format: 'pem', type: 'pkcs8'});
  const publicRaw = Buffer.from(publicKey.export({format: 'jwk'}).x, 'base64url');
  const now = 1793540000;
  const payload = makePayload(catalogue(), now * 1000);
  const envelope = Buffer.from(JSON.stringify(signPayload(payload, pem)));
  assert.equal(verifyPublication(envelope, publicRaw, now).model, MODEL);
  assert.throws(() => verifyPublication(envelope, Buffer.alloc(32), now));
  assert.throws(() => verifyPublication(envelope, publicRaw, now + 301));
  assert.throws(() => verifyPublication(envelope, publicRaw, now - 1));
  const changed = Buffer.from(JSON.stringify(signPayload({...payload, model: 'unqualified/model'}, pem)));
  assert.throws(() => verifyPublication(changed, publicRaw, now));
});
