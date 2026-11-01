import { strict as assert } from 'node:assert';
import test from 'node:test';
import { CatalogueError, inspectCatalogue, summarizeCatalogue } from '../timeweb-model-catalog.mjs';

test('catalogue names do not prove working inference or permit silent model substitution', async () => {
  const result = await inspectCatalogue('synthetic-key', async () => ({data:[
    {id:'openai/gpt-6-luna'}, {id:'gpt-6.1-sol'}, {id:'gpt-6-astra-2026-10-01'},
    {id:'gpt-6-sol'}, {id:'other/model', secret_metadata:'must not enter output'},
  ]}));
  assert.equal(result.status, 'catalogue_received');
  assert.deepEqual(result.requested_models.map(row=>row.advertised_ids), [
    ['openai/gpt-6-luna'], ['gpt-6.1-sol'], [],
  ]);
  assert.equal(result.inference_access_verified, false);
  assert.equal(result.qualification_passed, false);
  assert.equal(result.model_invocations, 0);
  assert.equal(JSON.stringify(result).includes('secret_metadata'), false);
});

test('invalid or missing credentials cause no network attempt', async () => {
  for (const value of ['', null, 'token\nheader:attack', 'x'.repeat(16385)]) {
    const result = await inspectCatalogue(value, async()=>{throw new Error('must not execute');});
    assert.equal(result.reason, 'gateway_credential_missing_or_invalid');
  }
});

test('an error cannot disclose headers, body or credential', async () => {
  const result = await inspectCatalogue('synthetic-secret', async()=>{
    throw new Error('Authorization Bearer synthetic-secret private-body');
  });
  assert.equal(result.reason, 'gateway_probe_failed');
  assert.equal(JSON.stringify(result).includes('synthetic-secret'), false);
  const denied = await inspectCatalogue('synthetic-secret', async()=>{throw new CatalogueError('gateway_http_401');});
  assert.equal(denied.reason, 'gateway_http_401');
});

test('malformed, duplicate and oversized catalogues do not produce availability claims', () => {
  for (const payload of [null, {}, {data:{}}, {data:[null]}, {data:[{id:'bad\nname'}]},
    {data:[{id:'gpt-6-luna'},{id:'gpt-6-luna'}]}, {data:new Array(5001)}]) {
    assert.throws(()=>summarizeCatalogue(payload), CatalogueError);
  }
});
