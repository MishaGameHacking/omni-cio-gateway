"""Adopt the owner's supplied Gateway key without creation, rotation or deletion.

The initial provider day limit is preserved, so normal setup cannot reset its
usage counter. A missing monthly cap may be added once. Only the reviewed
private staging and activation operations may change the existing runtime.
"""
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import re

import activate_owner55_ai as activation
import provision_owner55_ai as provision
from admin_owner55_ai import DiscardedOutput, source_proof
from owner_ai_admin_transport import require_admin_guard, transport_admin
from owner_ai_private_transport import PrivateTransportError

PROVIDER_LIMITS = {'day':'100', 'month':'2900'}

RUNTIME_INSPECTION = '''
import hmac,json,os
from pathlib import Path
FIELDS=['TIMEWEB_AI_TOKEN','ANALYST_OWNER_AI_KEY_ID','TIMEWEB_AI_BASE_URL','AI_TRANSPORT',
 'AI_ALLOWED_PROCESSING_REGIONS','AI_EXTERNAL_PROCESSING_APPROVED','AI_USER_DAILY_RUB',
 'AI_PROJECT_DAILY_RUB','AI_USER_MONTHLY_RUB','AI_PROJECT_MONTHLY_RUB',
 'ANALYST_OWNER_AI_DAY_LIMIT_ID','ANALYST_OWNER_AI_MONTH_LIMIT_ID']
for tier in ('FAST','STANDARD','PREMIUM'):
    FIELDS.append('AI_MODEL_'+tier)
    FIELDS.extend('AI_'+tier+'_'+suffix for suffix in ('TRANSPORT','PRICING_MODEL','PROCESSING_REGION',
      'TOKEN_PARAMETER','INPUT_TOKEN_ALLOWANCE','INPUT_RUB_PER_MILLION','OUTPUT_RUB_PER_MILLION','PRICING_VALID_UNTIL'))
def run(envelope):
    if os.getuid()!=0: raise RuntimeError('root_required')
    payload=envelope['payload']
    STAGING['verify_sources'](payload['source_sha256'])
    settings=STAGING['parse_environment'](STAGING['configuration_snapshot']()[0])
    result={'status':'runtime_inspected','server_id':9417611,
      'key_present':bool(settings.get('TIMEWEB_AI_TOKEN')),
      'key_matches_supplied':hmac.compare_digest(settings.get('TIMEWEB_AI_TOKEN',''),envelope.get('secret') or ''),
      'key_identity_matches':settings.get('ANALYST_OWNER_AI_KEY_ID')==payload['key_id'],
      'configuration_state':'other','service_active':False,'environment_file_verified':False,
      'process_configuration_loaded':False,'health_verified':False,'auth_boundary_verified':False,
      'gateway_metadata_verified':False,'last_failed_check':'none','configuration_changed':False,
      'missing_fields_mask':0,'different_fields_mask':0,'field_masks_verified':False}
    if all(settings.get(k)==v for k,v in STAGING['DISABLED'].items()):
        result['configuration_state']='staged_disabled'
    if all(settings.get(k)==v for k,v in ACTIVATION['ENABLED'].items()):
        result['configuration_state']='active'
    if all(settings.get(k)==v for k,v in {**ACTIVATION['ENABLED'],'AI_EXTERNAL_PROCESSING_APPROVED':'false'}.items()):
        result['configuration_state']='paused'
    selected={k:v for k,v in settings.items() if k.startswith(('AI_','TIMEWEB_AI_','ANALYST_OWNER_AI_'))}
    try:
        pid=ACTIVATION['systemctl']('show','analyst-ai-owner.service','--property=MainPID','--value')
        if not pid.isdigit() or int(pid)<=1: raise RuntimeError('invalid_pid')
        with Path('/proc/'+pid+'/environ').open('rb') as stream:
            raw=stream.read(512*1024+1)
        if len(raw)>512*1024: raise RuntimeError('environment_size')
        actual=dict(entry.split(b'=',1) for entry in raw.split(b'\\0') if entry)
        for index,key in enumerate(FIELDS):
            if key.encode() not in actual: result['missing_fields_mask']|=1<<index
            elif key in settings and actual[key.encode()]!=settings[key].encode():
                result['different_fields_mask']|=1<<index
        result['field_masks_verified']=True
    except BaseException: pass
    checks=[('service_active',lambda:ACTIVATION['systemctl']('is-active','analyst-ai-owner.service')=='active'),
      ('environment_file_verified',lambda:ACTIVATION['verify_environment_file']()),
      ('process_configuration_loaded',lambda:ACTIVATION['verify_running_configuration'](selected)),
      ('health_verified',lambda:ACTIVATION['read_get'](ACTIVATION['PUBLIC']+'/health')=={'status':'ok'}),
      ('auth_boundary_verified',lambda:ACTIVATION['read_get'](ACTIVATION['PUBLIC']+'/workspace/live?wait=0',allowed_status=401)),
      ('gateway_metadata_verified',lambda:ACTIVATION['verify_inference_key'](settings.get('TIMEWEB_AI_TOKEN','')))]
    for name,check in checks:
        try:
            value=check()
            result[name]=value is not False
        except BaseException:
            result['last_failed_check']=name
    return result
if __name__=='__main__':
    print(json.dumps(run(ENVELOPE)),flush=True)
'''


def inspect_runtime(transfer, sources, key_id, secret):
    need(isinstance(key_id,str) and provision.uuid_text(key_id)==key_id,'reviewed_key_identity_required')
    root=Path(__file__).resolve().parents[1]
    staging=(root/'deploy/stage_owner55_ai.py').read_text()
    active=(root/'deploy/activate_owner55_ai.py').read_text()
    operation=('support={"__name__":"owner_staging"}\nexec(compile('+repr(staging)+',"staging","exec"),support)\n'
        'active={"__name__":"owner_active","STAGING":support}\nexec(compile('+repr(active)+',"activation","exec"),active)\n'
        'exec(compile('+repr(RUNTIME_INSPECTION)+',"runtime-inspection","exec"),'
        '{"STAGING":support,"ACTIVATION":active,"ENVELOPE":ENVELOPE,"__name__":"__main__"})\n')
    fields=['key_present','key_matches_supplied','key_identity_matches','service_active',
        'environment_file_verified','process_configuration_loaded','health_verified',
        'auth_boundary_verified','gateway_metadata_verified','configuration_changed','field_masks_verified']
    contract={name:bool for name in fields}
    contract.update(status={'runtime_inspected'},server_id=int,missing_fields_mask=int,different_fields_mask=int,
        configuration_state={'other','staged_disabled','active','paused'},
        last_failed_check={'none','service_active','environment_file_verified','process_configuration_loaded',
                           'health_verified','auth_boundary_verified','gateway_metadata_verified'})
    return transfer(operation,{'source_sha256':sources,'key_id':key_id},secret,contract)


class AdoptionError(RuntimeError):
    def __init__(self, code, *, blocked=None):
        super().__init__(code)
        self.code, self.blocked = code, blocked


def need(condition, code):
    if not condition:
        raise AdoptionError(code)


class API(activation.ActivationAPI):
    PATCH_AMOUNTS = {0, 100, 2900}
    def request(self, method, path, body=None):
        if method == 'POST':
            need(re.fullmatch(re.escape(provision.KEYS)+r'/[0-9a-f-]{36}/entity-limits', path)
                 and body == {'entity_type':'aikey', 'limit_type':'month', 'money_limit':2900},
                 'only_missing_month_limit_may_be_created')
            return provision.CloudAPI.request(self, method, path, body)
        return super().request(method, path, body)


RUNTIME_REPAIR = '''
import fcntl,hmac,json,os,re,stat
from pathlib import Path
UNIT='/etc/systemd/system/analyst-ai-owner.service'
def unset_names():
    value=ACTIVATION['systemctl']('show','analyst-ai-owner.service','--property=UnsetEnvironment','--value')
    names=value.split()
    if len(names)>128 or any(re.fullmatch('[A-Z][A-Z0-9_]*',name) is None for name in names):
        raise RuntimeError('unsupported_unit_unset_syntax')
    return set(names)
def patch_unit(raw):
    section=''; lines=[]; removed=0
    for line in raw.decode('utf-8').splitlines(keepends=True):
        stripped=line.strip()
        if stripped.startswith('[') and stripped.endswith(']'): section=stripped
        key,sep,value=stripped.partition('=')
        if section=='[Service]' and sep and key.strip()=='UnsetEnvironment':
            names=value.split()
            if any(re.fullmatch('[A-Z][A-Z0-9_]*',name) is None for name in names):
                raise RuntimeError('unsupported_unit_unset_syntax')
            if 'TIMEWEB_AI_TOKEN' in names:
                remaining=[name for name in names if name!='TIMEWEB_AI_TOKEN']; removed+=1
                if remaining:
                    end=line[len(line.rstrip(chr(13)+chr(10))):]
                    lines.append(line.partition('=')[0]+'='+' '.join(remaining)+end)
                # Remove a sole-key directive; an empty assignment would RESET
                # and accidentally drop restrictions from earlier directives.
                continue
        lines.append(line)
    return ''.join(lines).encode('utf-8'),removed
def unit_snapshot(path):
    with os.fdopen(os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)),'rb') as stream:
        before=os.fstat(stream.fileno()); raw=stream.read(128*1024+1); after=os.fstat(stream.fileno())
    identity=STAGING['file_identity']
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_uid!=0
        or before.st_mode&0o022 or len(raw)>128*1024 or path.resolve(strict=True)!=path
        or identity(before)!=identity(after) or identity(after)!=identity(path.lstat())):
        raise RuntimeError('unit_snapshot_not_verified')
    return raw,identity(before)
def unit_plan():
    before=unset_names()
    if 'TIMEWEB_AI_TOKEN' not in before: return [],before
    fragment=ACTIVATION['systemctl']('show','analyst-ai-owner.service','--property=FragmentPath','--value')
    drops=ACTIVATION['systemctl']('show','analyst-ai-owner.service','--property=DropInPaths','--value').split()
    if fragment!=UNIT or len(drops)>16 or any(re.fullmatch(re.escape(UNIT)+r'[.]d/[A-Za-z0-9_.-]+[.]conf',p) is None for p in drops):
        raise RuntimeError('unit_paths_not_verified')
    plans=[]
    for name in [fragment,*drops]:
        path=Path(name); snapshot=unit_snapshot(path); desired,count=patch_unit(snapshot[0])
        if count: plans.append((path,snapshot,desired))
    if not plans: raise RuntimeError('unit_restriction_source_not_found')
    return plans,before
def write_unit(path,snapshot,desired):
    temporary=path.with_name(path.name+'.owner-ai-key-repair')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(desired); stream.flush(); os.fsync(stream.fileno())
        os.chown(temporary,snapshot[1][2],snapshot[1][3]); os.chmod(temporary,snapshot[1][4]&0o777)
        if unit_snapshot(path)!=snapshot: raise RuntimeError('unit_changed_before_write')
        os.replace(temporary,path)
        directory=os.open(path.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if temporary.exists(): temporary.unlink()
def apply_unit_plan(plans,before):
    if unset_names()!=before or any(unit_snapshot(path)!=snapshot for path,snapshot,_ in plans):
        raise RuntimeError('unit_changed_before_write')
    for path,snapshot,desired in plans: write_unit(path,snapshot,desired)
    if plans: ACTIVATION['systemctl']('daemon-reload')
    if unset_names()!=before-{'TIMEWEB_AI_TOKEN'}: raise RuntimeError('unit_unset_change_not_verified')
def run(envelope):
    result={'status':'blocked','server_id':9417611,'phase':'identity',
      'configuration_changed':False,'service_restarted':False,'process_configuration_loaded':False,
      'health_verified':False,'auth_boundary_verified':False,'key_matches_supplied':False,
      'public_feed_unchanged':False,'inference_called':False,'unit_configuration_changed':False}
    try:
        payload=envelope['payload']; kind=payload['action']
        if os.getuid()!=0 or kind not in {'repair','resume'}: return result
        with STAGING['LOCK'].open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            STAGING['verify_sources'](payload['source_sha256'])
            original=STAGING['configuration_snapshot']()
            settings=STAGING['parse_environment'](original[0])
            if settings.get('ANALYST_OWNER_AI_KEY_ID')!=payload['key_id']: return result
            result['key_matches_supplied']=hmac.compare_digest(settings.get('TIMEWEB_AI_TOKEN',''),envelope['secret'])
            if not result['key_matches_supplied']: return result
            if any(settings.get(k)!=v for k,v in ACTIVATION['ENABLED'].items() if k!='AI_EXTERNAL_PROCESSING_APPROVED'):
                return result
            result['phase']='unit_metadata'
            ACTIVATION['verify_environment_file']()
            result['phase']='unit_inspection'
            plans,before=unit_plan()
            if kind=='resume' and plans: return result
            feed=ACTIVATION['public_feed_pid']()
            expected={k:v for k,v in settings.items() if k.startswith(('AI_','TIMEWEB_AI_','ANALYST_OWNER_AI_'))}
            if kind=='resume':
                result['phase']='paused_process'
                if settings.get('AI_EXTERNAL_PROCESSING_APPROVED')!='false': return result
                ACTIVATION['verify_running_configuration'](expected)
            changes={'TIMEWEB_AI_TOKEN':envelope['secret'],'AI_EXTERNAL_PROCESSING_APPROVED':'true' if kind=='resume' else 'false'}
            expected.update(changes)
            result['phase']='configuration_write'
            desired=STAGING['replacement_environment'](original[0],changes)
            STAGING['atomic_configuration'](desired,original)
            result['configuration_changed']=True
            if STAGING['configuration_snapshot']()[0]!=desired: return result
            result['phase']='unit_write'
            apply_unit_plan(plans,before)
            result['unit_configuration_changed']=bool(plans)
            result['phase']='restart'
            ACTIVATION['systemctl']('restart','analyst-ai-owner.service')
            result['service_restarted']=True
            result['phase']='runtime_verification'
            ACTIVATION['readiness_after_restart'](expected)
            result.update(process_configuration_loaded=True,health_verified=True,auth_boundary_verified=True)
            result['public_feed_unchanged']=ACTIVATION['public_feed_pid']()==feed
            if not result['public_feed_unchanged']: return result
            result.update(status='activated' if kind=='resume' else 'repaired',phase='complete')
    except BaseException: pass
    return result
if __name__=='__main__': print(json.dumps(run(ENVELOPE)),flush=True)
'''


def repair_operation():
    root=Path(__file__).resolve().parents[1]
    staging=(root/'deploy/stage_owner55_ai.py').read_text()
    active=(root/'deploy/activate_owner55_ai.py').read_text()
    return ('support={"__name__":"owner_staging"}\nexec(compile('+repr(staging)+',"staging","exec"),support)\n'
        'active={"__name__":"owner_active","STAGING":support}\nexec(compile('+repr(active)+',"activation","exec"),active)\n'
        'exec(compile('+repr(RUNTIME_REPAIR)+',"runtime-repair","exec"),'
        '{"STAGING":support,"ACTIVATION":active,"ENVELOPE":ENVELOPE,"__name__":"__main__"})\n')


def recover(api,transfer,sources,key_id,secret,*,resume=False):
    provision.require_gateway_key(secret)
    activation.owned_key(api,key_id,'owner-supplied')
    identities=activation.limit_ids(api.request('GET',provision.KEYS+'/'+key_id+'/entity-limits'),
                                   key_id,{'day':'0','month':'0'})
    contract={name:bool for name in ['configuration_changed','service_restarted','process_configuration_loaded',
        'health_verified','auth_boundary_verified','key_matches_supplied','public_feed_unchanged','inference_called',
        'unit_configuration_changed']}
    contract.update(status={'blocked','activated','repaired'},server_id=int,
        phase={'identity','unit_metadata','unit_inspection','unit_write','paused_process','configuration_write',
               'restart','runtime_verification','complete'})
    if not resume:
        receipt=transfer(repair_operation(),{'action':'repair','key_id':key_id,'source_sha256':sources},secret,contract)
        activation.verify_limits(api,key_id,identities,{'day':'0','month':'0'})
        return {**receipt,'provider_zero_limits_verified':True}
    current=inspect_runtime(transfer,sources,key_id,secret)
    need(current['configuration_state']=='paused' and current['key_matches_supplied']
         and current['key_identity_matches'] and current['process_configuration_loaded']
         and current['health_verified'] and current['auth_boundary_verified']
         and current['gateway_metadata_verified'],'paused_runtime_not_verified')
    try:
        for period in ('day','month'):
            api.request('PATCH',provision.KEYS+'/'+key_id+'/entity-limits/'+identities[period],
                        {'money_limit':int(PROVIDER_LIMITS[period])})
        activation.verify_limits(api,key_id,identities,PROVIDER_LIMITS)
        receipt=transfer(repair_operation(),{'action':'resume','key_id':key_id,'source_sha256':sources},secret,contract)
        need(receipt['status']=='activated','runtime_resume_not_verified')
        activation.verify_limits(api,key_id,identities,PROVIDER_LIMITS)
        return {**receipt,'daily_cap_rub':'95','monthly_cap_rub':'2900',
            'provider_daily_limit_rub':'100','provider_30_day_limit_rub':'2900',
            'key_created':False,'key_rotated':False}
    except BaseException:
        raise AdoptionError('resume_requires_inspected_recovery',
            blocked=activation.block_provider(api,key_id,identities)) from None


def inventory(api, expected_id=None):
    rows = provision.keys(api)
    candidates = [row for row in rows if row.get('project_id') == 2941515]
    need(len(candidates) == 1, 'owner_project_key_not_unique')
    row = candidates[0]
    provision.validate_created_metadata(row, row['name'], row['id'])
    key_id = row['id']
    need(expected_id is None or expected_id == key_id, 'reviewed_key_identity_changed')
    payload = api.request('GET', provision.KEYS+'/'+key_id+'/entity-limits')
    rows, complete = provision.complete_collection(payload, 'ai_key_entity_limits')
    need(complete and len(rows) in (1,2), 'adoption_limits_incomplete')
    values, identities = {}, set()
    for limit in rows:
        need(isinstance(limit, dict), 'adoption_limit_invalid')
        period = limit.get('limit_type')
        identity = provision.uuid_text(limit.get('id'))
        money = provision.decimal_text(limit.get('money_limit'))
        need(period in PROVIDER_LIMITS and period not in values and identity is not None
             and identity not in identities and limit.get('ai_key_id') == key_id
             and limit.get('entity_id') == key_id and limit.get('entity_type') == 'aikey'
             and 'model_id' in limit and limit['model_id'] is None and money is not None,
             'adoption_limit_invalid')
        # Preserve stricter owner limits instead of replacing them with these
        # fixed reviewed defaults. Such cases require a separately sized config.
        need(Decimal(money) == Decimal(PROVIDER_LIMITS[period]), 'existing_limit_needs_individual_configuration')
        identities.add(identity)
        values[period] = identity
    need('day' in values, 'existing_daily_cap_required')
    return key_id, values


def inspect(api, transfer, sources, expected_id=None):
    finances = api.request('GET', provision.FINANCES).get('finances')
    need(isinstance(finances, dict) and finances.get('currency') == 'RUB', 'account_currency_not_rub')
    prices = provision.pricing(api, datetime.now(timezone.utc))
    key_id, limits = inventory(api, expected_id)
    operation = (Path(__file__).resolve().parents[1]/'deploy/stage_owner55_ai.py').read_text()
    receipt = transfer(operation, {'action':'preflight', 'source_sha256':sources}, None,
                       provision.PREFLIGHT_CONTRACT)
    provision.require_ready(receipt)
    return key_id, limits, prices, operation


def adopt(api, transfer, sources, secret, expected_id):
    need(isinstance(expected_id,str) and provision.uuid_text(expected_id)==expected_id,'reviewed_key_identity_required')
    provision.require_gateway_key(secret)
    key_id, identities, pricing, operation = inspect(api, transfer, sources, expected_id)
    # Recheck the exact inventory before adding a monthly limit. No existing
    # provider limit is patched during a successful adoption.
    need(inventory(api, key_id)[1] == identities, 'limits_changed_before_adoption')
    if 'month' not in identities:
        try:
            api.request('POST', provision.KEYS+'/'+key_id+'/entity-limits',
                        {'entity_type':'aikey', 'limit_type':'month', 'money_limit':2900})
        except BaseException:
            # No blind second POST: the first may have committed.
            raise AdoptionError('monthly_limit_creation_requires_readback') from None
        key_id, identities = inventory(api, key_id)
    need(set(identities) == {'day','month'}, 'monthly_limit_not_verified')
    private_started = False
    try:
        private_started = True
        stage = transfer(operation, {'action':'stage_disabled', 'key_id':key_id,
            'model':provision.MODEL, 'pricing':pricing, 'source_sha256':sources},
            secret, provision.staged_contract(key_id))
        need(stage == {'status':'staged_disabled', 'server_id':9417611, 'key_id':key_id,
            'model':provision.MODEL, 'daily_cap_rub':'0', 'monthly_cap_rub':'0',
            'existing_key_replaced':False, 'service_restarted':False, 'inference_called':False},
            'private_staging_not_verified')
        active_op = activation.operation_source()
        payload = {'key_id':key_id, 'model':provision.MODEL, 'pricing':pricing,
                   'source_sha256':sources, 'limit_ids':identities}
        expected = {'status':'activation_ready', 'server_id':9417611, 'key_id':key_id,
            'inference_key_authenticated':True, 'model_present':True,
            'configuration_changed':False, 'inference_probe_called':False}
        receipt = transfer(active_op, {**payload, 'action':'preflight_activation'}, None,
                           activation.receipt_contract(expected))
        need(receipt == expected, 'server_gateway_readiness_failed')
        activation.verify_limits(api, key_id, identities, PROVIDER_LIMITS)
        activation.owned_key(api, key_id, 'owner-supplied')
        expected = activation.activated_receipt(key_id, pricing)
        receipt = transfer(active_op, {**payload, 'action':'activate'}, None,
                           activation.receipt_contract(expected))
        need(receipt == expected, 'runtime_activation_not_verified')
        activation.verify_limits(api, key_id, identities, PROVIDER_LIMITS)
        return {**receipt, 'key_created':False, 'key_rotated':False,
            'provider_daily_limit_rub':'100', 'provider_30_day_limit_rub':'2900',
            'existing_provider_limits_patched':False, 'automatic_price_renewal_installed':False}
    except BaseException:
        blocked = activation.block_provider(api, key_id, identities) if private_started else None
        raise AdoptionError('adoption_requires_inspected_recovery', blocked=blocked) from None


def main():
    report, code = {'status':'not_activated'}, 1
    try:
        with redirect_stdout(DiscardedOutput()), redirect_stderr(DiscardedOutput()):
            require_admin_guard()
            action = os.environ.get('OWNER_SUPPLIED_AI_ACTION')
            need(action in {'inspect', 'adopt_activate', 'inspect_runtime','repair_runtime','resume_runtime'}, 'reviewed_adoption_action_required')
            api = API(os.environ['TIMEWEB_CLOUD_TOKEN'])
            sources = source_proof(os.environ)
            if action == 'inspect':
                key_id, identities, _, _ = inspect(api, transport_admin, sources)
                report = {'status':'supplied_key_ready', 'key_id':key_id,
                    'provider_daily_limit_rub':'100', 'provider_monthly_limit_present':'month' in identities,
                    'server_configuration_changed':False, 'inference_called':False}
            elif action == 'inspect_runtime':
                report = inspect_runtime(transport_admin, sources, os.environ.get('OWNER_SUPPLIED_AI_KEY_ID'),
                                         os.environ['TIMEWEB_AI_TOKEN'])
            elif action in {'repair_runtime','resume_runtime'}:
                report=recover(api,transport_admin,sources,os.environ.get('OWNER_SUPPLIED_AI_KEY_ID'),
                               os.environ['TIMEWEB_AI_TOKEN'],resume=action=='resume_runtime')
            else:
                report = adopt(api, transport_admin, sources, os.environ['TIMEWEB_AI_TOKEN'],
                               os.environ.get('OWNER_SUPPLIED_AI_KEY_ID'))
            code = 1 if report.get('status')=='blocked' else 0
    except AdoptionError as error:
        report.update(reason=error.code, provider_zero_limits_verified=error.blocked)
    except PrivateTransportError as error:
        report.update(reason=error.code, private_operation_started=error.operation_started,
                      temporary_ssh_key_removed=error.temporary_key_removed)
    except BaseException:
        report['reason'] = 'supplied_key_setup_precondition_failed'
    finally:
        os.environ.pop('TIMEWEB_AI_TOKEN', None)
        os.environ.pop('TIMEWEB_CLOUD_TOKEN', None)
    print('OWNER_SUPPLIED_AI_SETUP='+json.dumps(report, sort_keys=True), flush=True)
    raise SystemExit(code)


if __name__ == '__main__':
    main()
