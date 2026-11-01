/** Catalogue/tariff metadata only. Never invokes a model or changes an account. */
import {writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import {gatewayRequest, GatewayError, validCredential} from './timeweb-ai-http.mjs';

function rows(value) {
  const result = Array.isArray(value) ? value : value && typeof value === 'object' ? Object.values(value) : null;
  if (!result || result.length > 5000 || result.some(row => !row || typeof row !== 'object' || Array.isArray(row))) {
    throw new GatewayError('catalogue_shape_invalid');
  }
  return result;
}

function smallScalar(value) {
  return value === null || typeof value === 'boolean' || (typeof value === 'number' && Number.isFinite(value)) ||
    (typeof value === 'string' && value.length <= 400);
}

export function summarizePrices(catalogue, dictionary) {
  const models = rows(catalogue?.models);
  const parameters = rows(dictionary?.model_parameters);
  const identityKeys = ['id','name','slug','model','model_id','api_name','api_id','is_deprecated','is_stopped'];
  const requested = models.filter(row => identityKeys.some(key => typeof row[key] === 'string' &&
    /gpt[ -]?6([. -]?1)?[ /_-]?(luna|sol|astra)/i.test(row[key])));
  const selected = requested.map(row => ({
    identity:Object.fromEntries(identityKeys.filter(key => key in row && smallScalar(row[key])).map(key => [key,row[key]])),
    parameter_values:Object.fromEntries(Object.entries(row.parameter_values ?? {}).filter(([key,value]) =>
      /^[a-zA-Z0-9_]{1,80}$/.test(key) && smallScalar(value))),
  }));
  const costParameters = parameters.filter(row => Object.values(row).some(value =>
    typeof value === 'string' && /cost|price|руб|RUB/i.test(value)));
  return {models:selected, price_parameters:costParameters.map(row => Object.fromEntries(
    Object.entries(row).filter(([key,value]) => ['key','id','name','slug','code','description','unit','units','type'].includes(key) && smallScalar(value)))),
    catalogue_count:models.length};
}

export async function inspectPrices(apiKey, request = gatewayRequest) {
  const report = {schema_version:1,checked_at_utc:new Date().toISOString(),provider:'Timeweb AI Gateway',
    source:'https://api.timeweb.cloud/api/v3/cloud-ai/models',status:'unverified',
    model_invocations:0,financial_orders:0,owner_data_transmitted:false};
  try {
    validCredential(apiKey);
    const catalogue = await request('prices',apiKey);
    const units = await request('price_units',apiKey);
    Object.assign(report,summarizePrices(catalogue,units),{status:'metadata_received'});
  } catch(error) {
    report.status='unavailable';
    report.reason=error instanceof GatewayError ? error.code : 'pricing_probe_failed';
  }
  return report;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const report=await inspectPrices(process.env.TIMEWEB_CLOUD_TOKEN ?? '');
  await writeFile('timeweb-model-pricing.json',JSON.stringify(report,null,2)+'\n',{mode:0o600});
  console.log(JSON.stringify({status:report.status,reason:report.reason,model_invocations:0,report:'timeweb-model-pricing.json'}));
  process.exitCode=report.status === 'metadata_received' ? 0 : 2;
}
