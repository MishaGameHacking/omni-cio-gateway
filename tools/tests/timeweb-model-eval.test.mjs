import {strict as assert} from 'node:assert';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import {MODELS,MAX_OUTPUT_TOKENS,requestPayload,responseUsage,responseAnswer,scoreAnswer,tariffs,runBenchmark} from '../timeweb-model-eval.mjs';
import {GatewayError} from '../timeweb-ai-http.mjs';

const fixture=JSON.parse(await readFile(new URL('../fixtures/portfolio-action-v1.json',import.meta.url),'utf8'));
const pricing=JSON.parse(await readFile(new URL('../../docs/evidence/2026-11-01-timeweb-model-pricing.json',import.meta.url),'utf8'));
const now=()=>Date.parse(pricing.checked_at_utc)+1000;
function response(model,scenario) {
  return {model,status:'completed',error:null,incomplete_details:null,usage:{input_tokens:100,output_tokens:30,total_tokens:130},
    output:[{type:'message',role:'assistant',status:'completed',content:[{type:'output_text',text:JSON.stringify({
      decision:scenario.expected,source_ids:scenario.required_sources,reason:'Решение проверено по указанным фактам и ограничениям.'})}]}]};
}

test('a proposal request has no answers, credentials, tools or storage and includes an output cap',()=>{
  for(const model of MODELS) {
    const p=requestPayload(model,fixture,fixture.cases[0]);
    assert.equal(p.max_output_tokens,MAX_OUTPUT_TOKENS);
    assert.equal(p.store,false);assert.deepEqual(p.tools,[]);assert.equal(p.tool_choice,'none');
    assert.deepEqual(JSON.parse(p.input),fixture.cases[0].facts);
    assert.equal(JSON.stringify(p).includes('required_sources'),false);
    assert.equal(JSON.stringify(p).includes('expected'),false);
  }
});

test('references, known policy violations and extra fields cannot pass by producing valid JSON',()=>{
  const scenario=fixture.cases[0];
  const good={decision:'hold',source_ids:['mandate'],reason:'Новый риск запрещён действующими условиями.'};
  assert.equal(scoreAnswer(scenario,good).passed,true);
  assert.equal(scoreAnswer(scenario,{...good,decision:'approve'}).failure,'decision_mismatch');
  assert.equal(scoreAnswer(scenario,{...good,source_ids:['invented-source']}).failure,'source_binding');
  assert.equal(scoreAnswer(scenario,{...good,source_ids:['mandate','mandate']}).failure,'source_binding');
  assert.equal(scoreAnswer(scenario,{...good,override:true}).failure,'answer_schema');
});

test('provider identity, complete output, usage and absence of tools are independently checked',()=>{
  const base=response(MODELS[0],fixture.cases[0]);
  assert.equal(responseAnswer(base).decision,'hold');
  assert.equal(responseUsage(base,MODELS[0],3000).total_tokens,130);
  assert.throws(()=>responseUsage({...base,model:MODELS[1]},MODELS[0],3000),/model_mismatch/);
  assert.throws(()=>responseUsage({...base,usage:{input_tokens:100,output_tokens:1601,total_tokens:1701}},MODELS[0],3000),/usage_invalid/);
  assert.throws(()=>responseUsage({...base,usage:{input_tokens:100,output_tokens:30,total_tokens:129}},MODELS[0],3000),/usage_invalid/);
  assert.throws(()=>responseAnswer({...base,status:'incomplete'}),/not_complete/);
  assert.throws(()=>responseAnswer({...base,output:[{type:'function_call'}]}),/unexpected_output/);
});

test('tariffs must match the exact available models and be fresh; values are conservatively per token',()=>{
  assert.equal(tariffs(pricing,now())[MODELS[2]].output,6750000n);
  assert.throws(()=>tariffs(pricing,now()+86400000),/stale/);
  const copy=structuredClone(pricing);
  copy.models=copy.models.filter(row=>row.identity.model_name!==MODELS[1]);
  assert.throws(()=>tariffs(copy,now()),/unavailable/);
});

test('each billable request has a durable reservation; a correct synthetic suite does not qualify a portfolio manager',async()=>{
  let latest,calls=0;
  const report=await runBenchmark({apiKey:'synthetic-key',fixture,pricing,now,
    persist:async value=>{latest=structuredClone(value);},
    request:async(route,key,payload)=>{
      assert.equal(route,'responses');assert.equal(key,'synthetic-key');
      assert.equal(latest.attempts.at(-1).state,'pending_unknown');
      assert.ok(Number(latest.unresolved_reservations_rub)>0);
      assert.ok(Number(latest.total_priced_and_reserved_rub)<=60);
      return response(payload.model,fixture.cases[calls++%10]);
    }});
  assert.equal(calls,30);
  assert.ok(report.models.every(m=>m.synthetic_suite_passed&&m.passed===10));
  assert.equal(report.portfolio_manager_qualified,false);
  assert.equal(report.invoiced_cost_verified,false);
  assert.equal(report.unresolved_reservations_rub,'0.000000000');
  assert.equal(JSON.stringify(report).includes('synthetic-key'),false);
});

test('unknown outcome is never retried and keeps its budget reservation without leaking upstream details',async()=>{
  let calls=0;
  const report=await runBenchmark({apiKey:'synthetic-key',fixture,pricing,now,request:async()=>{
    calls++;throw new Error('private upstream body or credential synthetic-key');
  }});
  assert.equal(calls,3); // one attempt per different model, no repeated proposal
  assert.ok(report.models.every(m=>m.attempted===1&&m.stopped_reason==='unresolved_request_no_retry'));
  assert.ok(Number(report.unresolved_reservations_rub)>0);
  assert.equal(report.priced_usage_upper_estimate_rub,'0.000000000');
  assert.equal(JSON.stringify(report).includes('synthetic-key'),false);
});

test('a small budget prevents all POSTs and malformed usage stops the whole run',async()=>{
  let calls=0;
  const noMoney=await runBenchmark({apiKey:'synthetic-key',fixture,pricing,now,budget:1n,request:async()=>{calls++;}});
  assert.equal(calls,0);assert.equal(noMoney.model_invocations,0);
  const wrongModel=await runBenchmark({apiKey:'synthetic-key',fixture,pricing,now,request:async()=>{
    calls++;return response('substituted-model',fixture.cases[0]);
  }});
  assert.equal(calls,1);assert.equal(wrongModel.stopped_reason,'provider_identity_or_usage_unverified');
  assert.ok(Number(wrongModel.unresolved_reservations_rub)>0);
});

test('incomplete output with known usage is charged conservatively and never accepted',async()=>{
  const result=await runBenchmark({apiKey:'synthetic-key',fixture,pricing,now,request:async(_r,_k,p)=>
    ({...response(p.model,fixture.cases[0]),status:'incomplete'})});
  assert.equal(result.attempts.length,30);
  assert.ok(result.attempts.every(a=>!a.passed&&a.failure==='response_not_complete'));
  assert.ok(Number(result.priced_usage_upper_estimate_rub)>0);
  assert.equal(result.unresolved_reservations_rub,'0.000000000');
});
