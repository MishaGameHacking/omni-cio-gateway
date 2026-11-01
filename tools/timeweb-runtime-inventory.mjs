/** Read-only hosting inventory. No credentials, addresses or names in output. */
import https from 'node:https';
import {writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';

const PATHS = Object.freeze({servers:'/api/v1/servers?limit=100&offset=0', presets:'/api/v1/presets/servers',
  os:'/api/v1/os/servers', costs:'/api/v1/account/services/cost', ips:'/api/v1/floating-ips'});
class InventoryError extends Error { constructor(code) { super(code); this.code = code; } }

export function readCloud(name, token) {
  if (!Object.hasOwn(PATHS,name) || typeof token !== 'string' || !/^[\x21-\x7e]{16,16384}$/.test(token)) {
    throw new InventoryError('inventory_route_or_credential_invalid');
  }
  return new Promise((resolve,reject) => {
    let done=false, timer;
    const finish=(error,value)=>{if(done)return;done=true;clearTimeout(timer);error?reject(error):resolve(value);};
    const request=https.request({hostname:'api.timeweb.cloud',path:PATHS[name],method:'GET',
      headers:{Authorization:`Bearer ${token}`,Accept:'application/json','Accept-Encoding':'identity'}},response=>{
      if(response.statusCode!==200){response.destroy();finish(new InventoryError(`inventory_http_${response.statusCode}`));return;}
      if(!['','identity'].includes(String(response.headers['content-encoding']??'').toLowerCase())){
        response.destroy();finish(new InventoryError('inventory_encoding_invalid'));return;
      }
      const chunks=[];let bytes=0;
      response.on('data',chunk=>{bytes+=chunk.length;if(bytes>2*1024*1024){response.destroy();finish(new InventoryError('inventory_response_oversized'));}else chunks.push(chunk);});
      response.on('error',()=>finish(new InventoryError('inventory_response_incomplete')));
      response.on('aborted',()=>finish(new InventoryError('inventory_response_incomplete')));
      response.on('end',()=>{try{finish(null,JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(Buffer.concat(chunks))));}
        catch{finish(new InventoryError('inventory_json_invalid'));}});
    });
    timer=setTimeout(()=>{request.destroy();finish(new InventoryError('inventory_timeout'));},20000);
    request.on('error',()=>finish(new InventoryError('inventory_connection_failed')));
    request.end();
  });
}

const numericKeys=['id','cpu','ram','disk','size','bandwidth','price','price_month','price_day','preset_id','configurator_id',
  'cost','total_cost','service_id','project_id'];
const textKeys=['location','status','type','disk_type','currency','currency_code','os_name','version','availability_zone'];
function safeRecord(row) {
  if(!row||typeof row!=='object'||Array.isArray(row))throw new InventoryError('inventory_record_invalid');
  return Object.fromEntries([
    ...numericKeys.filter(k=>typeof row[k]==='number'&&Number.isFinite(row[k])&&row[k]>=0).map(k=>[k,row[k]]),
    ...textKeys.filter(k=>typeof row[k]==='string'&&/^[A-Za-z0-9 ._-]{1,80}$/.test(row[k])).map(k=>[k,row[k]]),
  ]);
}
function rows(value, keys) {
  const key=keys.find(k=>Array.isArray(value?.[k]));
  if(!key||value[key].length>2000)throw new InventoryError('inventory_list_invalid');
  return value[key];
}

export function summarizeInventory(servers, presets, operatingSystems, costs, ips) {
  const active=rows(servers,['servers']).map(row=>({...safeRecord(row),
    matches_project_name:typeof row.name==='string'&&/analyst|omnicio|omni-cio/i.test(row.name),
    disk_summaries:Array.isArray(row.disks)?row.disks.map(d=>safeRecord(d)):[]}));
  const plans=rows(presets,['server_presets','presets']).map(row=>safeRecord(row));
  const systems=rows(operatingSystems,['servers_os','os','operating_systems']).map(row=>({...safeRecord(row),
    ...(typeof row.name==='string'&&/^[A-Za-z0-9 ._-]{1,80}$/.test(row.name)?{os_name:row.name}:{})}));
  const costsSummary=costs?rows(costs,['services_costs']).map(row=>({...safeRecord(row),
    services:Array.isArray(row.services)?row.services.map(s=>safeRecord(s)):[]})):null;
  const ipSummary=ips?rows(ips,['ips']).map(row=>({...safeRecord(row),
    is_ddos_guard:row.is_ddos_guard===true,is_attached:Boolean(row.resource_id||row.resource),
    ...(typeof row.id==='string'&&/^[a-zA-Z0-9-]{1,80}$/.test(row.id)?{resource_id:row.id}:{})})):null;
  const selected=rows(presets,['server_presets','presets']).filter(row=>[6749,6759].includes(row.id)).map(row=>({
    ...safeRecord(row), description:typeof row.description==='string'?row.description.slice(0,600):null,
    tags:Array.isArray(row.tags)?row.tags.filter(v=>typeof v==='string'&&v.length<100):[],
    additional_pricing_fields:Object.fromEntries(Object.entries(row).filter(([k,v])=>/price|cost|ipv4|ip_included/.test(k)&&
      /^[a-z_]{1,80}$/.test(k)&&(['boolean','number'].includes(typeof v)||typeof v==='string'&&v.length<100)))}));
  return {servers:active,presets:plans,selected_public_presets:selected,operating_systems:systems,server_count:active.length,
    reported_server_total:Number.isInteger(servers?.meta?.total)?servers.meta.total:null,
    server_inventory_complete:Number.isInteger(servers?.meta?.total)&&servers.meta.total===active.length,
    active_service_costs:costsSummary,floating_ips:ipSummary,
    preset_count:plans.length,includes_secrets_or_network_addresses:false,
    plan_prices_are_complete_invoice:false,resources_created:0,resources_changed:0};
}

export async function inspectRuntime(token, request=readCloud) {
  const report={schema_version:1,checked_at_utc:new Date().toISOString(),status:'unverified',
    source:'https://api.timeweb.cloud',api_requests_read_only:true,financial_orders:0,model_invocations:0};
  try {
    const results=await Promise.allSettled(['servers','presets','os','costs','ips'].map(name=>request(name,token)));
    const failed=results.find(result=>result.status==='rejected');
    if(failed)throw failed.reason;
    Object.assign(report,summarizeInventory(...results.map(result=>result.value)),{status:'received'});
  } catch(error) {
    report.status='unavailable';
    report.reason=error instanceof InventoryError?error.code:'inventory_failed';
  }
  return report;
}

if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
  if(process.env.COMPUTERNAME!=='LAPTOP-NPSGA016'||!/^\d+$/.test(process.env.GITHUB_RUN_ID??''))throw new InventoryError('inventory_runner_required');
  const report=await inspectRuntime(process.env.TIMEWEB_CLOUD_TOKEN??'');
  const data=JSON.stringify(report,null,2)+'\n';
  const destination=`C:/actions-runner-2/_work/_tool/analyst-evidence/timeweb-runtime-inventory-${process.env.GITHUB_RUN_ID}.json`;
  await writeFile(destination,data,{flag:'wx',mode:0o600});
  console.log(JSON.stringify({status:report.status,reason:report.reason,sha256:createHash('sha256').update(data).digest('hex'),
    server_count:report.server_count,resources_created:0,model_invocations:0}));
  process.exitCode=report.status==='received'?0:2;
}
