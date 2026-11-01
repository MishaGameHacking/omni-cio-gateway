/** Bounded synthetic qualification. No broker access, owner facts, tools or retry. */
import {readFile,writeFile,open,rename} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {gatewayRequest,GatewayError,validCredential} from './timeweb-ai-http.mjs';

export const MODELS = Object.freeze(['openai/gpt-6-luna','openai/gpt-6.1-sol','openai/gpt-6-astra']);
export const MAX_OUTPUT_TOKENS = 1600;
export const BUDGET_NANORUB = 60_000_000_000n;
const NANO = 1_000_000_000n;
export function rub(value) { return `${value/NANO}.${(value%NANO).toString().padStart(9,'0')}`; }

function rate(value) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0 || value > 1) throw new GatewayError('tariff_invalid');
  return BigInt(Math.ceil(value*Number(NANO)));
}

export function tariffs(report, now=Date.now()) {
  if (report?.status !== 'metadata_received' || report.source !== 'https://api.timeweb.cloud/api/v3/cloud-ai/models' ||
    !Number.isFinite(Date.parse(report.checked_at_utc)) || Date.parse(report.checked_at_utc)>now ||
    now-Date.parse(report.checked_at_utc)>86400000 || !Array.isArray(report.models)) throw new GatewayError('tariffs_missing_or_stale');
  return Object.fromEntries(MODELS.map(model=>{
    const matches=report.models.filter(row=>row.identity?.model_name === model);
    if(matches.length!==1 || matches[0].identity.is_stopped!==false || matches[0].identity.is_deprecated!==false) {
      throw new GatewayError('tariff_model_unavailable');
    }
    const p=matches[0].parameter_values;
    const input=rate(p?.cost_in), output=rate(p?.cost_out), write=rate(p?.cost_cache_write);
    // Raw v3 values are treated as RUB/token, not divided by a million.
    // All input is priced at the larger normal/cache-write rate. This is a
    // conservative observation, not an invoice; cache discounts are ignored.
    return [model,{input:write>input?write:input,output}];
  }));
}

export function requestPayload(model, fixture, scenario) {
  if(!MODELS.includes(model)) throw new GatewayError('model_not_allowed');
  return {model, instructions:fixture.prompt, input:JSON.stringify(scenario.facts),
    store:false, stream:false, tools:[], tool_choice:'none', parallel_tool_calls:false,
    truncation:'disabled', max_output_tokens:MAX_OUTPUT_TOKENS,
    reasoning:{effort:model==='openai/gpt-6-luna'?'none':'low'},
    text:{format:{type:'json_schema',name:'portfolio_action_review',strict:true,
      schema:{type:'object',properties:{decision:{type:'string',enum:['approve','hold','review']},
        source_ids:{type:'array',items:{type:'string',enum:['mandate','broker','research']}},reason:{type:'string'}},
        required:['decision','source_ids','reason'],additionalProperties:false}}}};
}

export function scoreAnswer(scenario, answer) {
  if(!answer || typeof answer!=='object' || Array.isArray(answer) ||
    Object.keys(answer).sort().join(',')!=='decision,reason,source_ids') return {passed:false,failure:'answer_schema'};
  const refs=answer.source_ids;
  if(!Array.isArray(refs)||!refs.length||new Set(refs).size!==refs.length||
    refs.some(ref=>typeof ref!=='string'||!scenario.facts.sources.includes(ref))||
    scenario.required_sources.some(ref=>!refs.includes(ref))) return {passed:false,failure:'source_binding'};
  if(typeof answer.reason!=='string'||[...answer.reason].length<10||[...answer.reason].length>600) {
    return {passed:false,failure:'explanation_required'};
  }
  if(answer.decision!==scenario.expected) return {passed:false,failure:'decision_mismatch'};
  return {passed:true,failure:null};
}

export function responseUsage(response, model, inputBound) {
  if(!response || ![model,model.slice('openai/'.length)].includes(response.model)) throw new GatewayError('response_model_mismatch');
  const u=response.usage;
  if(!u || ![u.input_tokens,u.output_tokens,u.total_tokens].every(Number.isSafeInteger) ||
    u.input_tokens<1 || u.input_tokens>inputBound || u.output_tokens<0 || u.output_tokens>MAX_OUTPUT_TOKENS ||
    u.total_tokens!==u.input_tokens+u.output_tokens) throw new GatewayError('response_usage_invalid');
  return {input_tokens:u.input_tokens,output_tokens:u.output_tokens,total_tokens:u.total_tokens};
}

export function responseAnswer(response) {
  if(response.status!=='completed'||response.error||response.incomplete_details) throw new GatewayError('response_not_complete');
  if(!Array.isArray(response.output)||response.output.length>10||response.output.some(row=>!['reasoning','message'].includes(row?.type))) {
    throw new GatewayError('response_unexpected_output');
  }
  const messages=response.output.filter(row=>row.type==='message');
  if(messages.length!==1 || messages[0].role!=='assistant' || messages[0].status!=='completed' ||
    !Array.isArray(messages[0].content)||messages[0].content.length!==1||messages[0].content[0].type!=='output_text') {
    throw new GatewayError('response_message_invalid');
  }
  const value=messages[0].content[0].text;
  if(typeof value!=='string'||Buffer.byteLength(value,'utf8')>8192) throw new GatewayError('response_text_invalid');
  try {return JSON.parse(value);} catch {throw new GatewayError('answer_not_json');}
}

function validateFixture(fixture) {
  const ids=['zero_loss','reserve','reinvest_existing','bond_full_cost','stale_price','unverified_rating',
    'unsettled_income','coupon_is_not_total_return','reduce_concentration','source_prompt_injection'];
  if(fixture?.schema_version!==1||typeof fixture.prompt!=='string'||!Array.isArray(fixture.cases)||
    fixture.cases.length!==10||fixture.cases.some((c,i)=>c.id!==ids[i]||!c.facts||!Array.isArray(c.required_sources))) {
    throw new GatewayError('fixture_invalid');
  }
}

export async function runBenchmark({apiKey,fixture,pricing,request=gatewayRequest,persist=async()=>{},
  now=()=>Date.now(),budget=BUDGET_NANORUB}) {
  validCredential(apiKey); validateFixture(fixture);
  if(typeof budget!=='bigint'||budget<=0n||budget>BUDGET_NANORUB) throw new GatewayError('budget_invalid');
  const prices=tariffs(pricing,now());
  const report={schema_version:1,started_at_utc:new Date(now()).toISOString(),status:'running',
    protocol:'Responses API / strict JSON schema',fixture_sha256:createHash('sha256').update(JSON.stringify(fixture)).digest('hex'),
    provider:'Timeweb AI Gateway',financial_orders:0,owner_data_transmitted:false,automatic_retries:0,
    client_budget_rub:rub(budget),pricing_source:pricing.source,pricing_observed_at_utc:pricing.checked_at_utc,
    pricing_method:'Raw tariff as RUB/token; all input at max(input, cache-write), discounts ignored; provider invoice not verified.',
    invoiced_cost_verified:false,portfolio_manager_qualified:false,attempts:[],models:[]};
  let charged=0n,held=0n,stopAll=false;
  const save=async()=>{
    report.priced_usage_upper_estimate_rub=rub(charged);
    report.unresolved_reservations_rub=rub(held);
    report.total_priced_and_reserved_rub=rub(charged+held);
    await persist(report);
  };
  await save();
  for(const model of MODELS) {
    const result={model,attempted:0,verified_responses:0,passed:0,total_cases:fixture.cases.length,
      synthetic_suite_passed:false,portfolio_manager_qualified:false};
    report.models.push(result);
    for(const scenario of fixture.cases) {
      const payload=requestPayload(model,fixture,scenario);
      const inputBound=Buffer.byteLength(JSON.stringify(payload),'utf8')+2048;
      if(inputBound>12000) throw new GatewayError('input_budget_invalid');
      const cost=(u)=>BigInt(u.input_tokens)*prices[model].input+BigInt(u.output_tokens)*prices[model].output;
      const reserve=cost({input_tokens:inputBound,output_tokens:MAX_OUTPUT_TOKENS});
      if(charged+held+reserve>budget) {result.stopped_reason='test_budget_exhausted';break;}
      const attempt={model,case_id:scenario.id,expected:scenario.expected,state:'pending_unknown',
        request_sha256:createHash('sha256').update(JSON.stringify(payload)).digest('hex'),
        input_token_bound:inputBound,max_output_tokens:MAX_OUTPUT_TOKENS,reserved_rub:rub(reserve),
        started_at_utc:new Date(now()).toISOString(),passed:false,failure:'not_completed'};
      report.attempts.push(attempt); result.attempted++; held+=reserve;
      // Durable checkpoint BEFORE a billable POST. Unknown outcomes keep reserve.
      await save();
      const started=now();
      try {
        const response=await request('responses',apiKey,payload);
        attempt.returned_model=typeof response?.model==='string'&&/^[A-Za-z0-9_./:-]{1,160}$/.test(response.model)?response.model:null;
        attempt.usage=responseUsage(response,model,inputBound);
        const actual=cost(attempt.usage);
        held-=reserve; charged+=actual;
        attempt.priced_usage_upper_estimate_rub=rub(actual);
        attempt.state='response_accounted'; result.verified_responses++;
        const answer=responseAnswer(response);
        Object.assign(attempt,scoreAnswer(scenario,answer));
        // Only bounded, schema-checked fields from synthetic scenarios are saved.
        if(typeof answer?.decision==='string'&&['approve','hold','review'].includes(answer.decision)) attempt.decision=answer.decision;
        if(!attempt.failure||attempt.failure==='decision_mismatch') attempt.answer=answer;
        if(attempt.passed) result.passed++;
      } catch(error) {
        attempt.failure=error instanceof GatewayError?error.code:'evaluation_failed';
        if(attempt.state==='pending_unknown') {
          result.stopped_reason='unresolved_request_no_retry';
          if(['response_model_mismatch','response_usage_invalid'].includes(attempt.failure)) stopAll=true;
        }
      }
      attempt.latency_ms=Math.max(0,now()-started);
      await save();
      if(result.stopped_reason) break;
    }
    result.synthetic_suite_passed=result.passed===fixture.cases.length;
    const latencies=report.attempts.filter(a=>a.model===model&&a.state==='response_accounted').map(a=>a.latency_ms).sort((a,b)=>a-b);
    result.latency_ms=latencies.length?{min:latencies[0],max:latencies.at(-1),median:
      (latencies[Math.floor((latencies.length-1)/2)]+latencies[Math.ceil((latencies.length-1)/2)])/2}:null;
    await save();
    if(stopAll) {report.stopped_reason='provider_identity_or_usage_unverified';break;}
  }
  report.status='completed'; report.completed_at_utc=new Date(now()).toISOString();
  report.model_invocations=report.attempts.length;
  await save();return report;
}

if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href) {
  const output='timeweb-model-evaluation.json';
  try {
    // A rerun in the same directory must never silently repeat paid attempts.
    const file=await open(output,'wx',0o600); await file.close();
    const fixture=JSON.parse(await readFile(new URL('./fixtures/portfolio-action-v1.json',import.meta.url),'utf8'));
    const pricing=JSON.parse(await readFile(new URL('../docs/evidence/2026-11-01-timeweb-model-pricing.json',import.meta.url),'utf8'));
    const persist=async report=>{
      await writeFile(output+'.tmp',JSON.stringify(report,null,2)+'\n',{mode:0o600});
      await rename(output+'.tmp',output);
    };
    const report=await runBenchmark({apiKey:process.env.TIMEWEB_AI_TOKEN??'',fixture,pricing,persist});
    console.log(JSON.stringify({status:report.status,models:report.models.map(m=>({model:m.model,passed:m.passed,total:m.total_cases,
      stopped_reason:m.stopped_reason})),priced_and_reserved_rub:report.total_priced_and_reserved_rub,report:output}));
    process.exitCode=report.models.every(m=>m.synthetic_suite_passed)?0:2;
  } catch(error) {
    console.log(JSON.stringify({status:'not_completed',reason:error instanceof GatewayError?error.code:'evaluation_local_failure',report:output}));
    process.exitCode=2;
  }
}
