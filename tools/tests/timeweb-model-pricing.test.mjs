import {strict as assert} from 'node:assert';
import test from 'node:test';
import {inspectPrices,summarizePrices} from '../timeweb-model-pricing.mjs';
import {gatewayRequest,GatewayError} from '../timeweb-ai-http.mjs';

test('report preserves provider tariff units but omits unrelated metadata',()=>{
  const result=summarizePrices({models:[{id:17,name:'GPT-6.1 Sol',api_name:'openai/gpt-6.1-sol',is_stopped:false,
    secret:'must-not-leak',parameter_values:{cost_input:200,cost_output:1000}},{name:'Other model'}]},
    {model_parameters:[{key:'cost_input',unit:'RUB / 1M tokens',description:'Input price'}, {key:'context',unit:'tokens'}]});
  assert.equal(result.models.length,1);
  assert.equal(result.models[0].parameter_values.cost_input,200);
  assert.equal(result.price_parameters[0].unit,'RUB / 1M tokens');
  assert.equal(JSON.stringify(result).includes('must-not-leak'),false);
});

test('pricing lookup is read only and never emits an upstream error or missing credential',async()=>{
  let calls=0;
  const missing=await inspectPrices('',async()=>{calls++;});
  assert.equal(calls,0);
  assert.equal(missing.status,'unavailable');
  const failed=await inspectPrices('synthetic-secret',async()=>{throw new Error('synthetic-secret private payload');});
  assert.equal(JSON.stringify(failed).includes('synthetic-secret'),false);
  assert.equal(failed.model_invocations,0);
  assert.throws(()=>gatewayRequest('arbitrary-url','synthetic-secret'),GatewayError);
  assert.throws(()=>gatewayRequest('prices','synthetic-secret',{}),GatewayError);
  assert.throws(()=>summarizePrices({models:[]},{model_parameters:null}),GatewayError);
});
