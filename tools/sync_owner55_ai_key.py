"""Deliver an owner-rotated AI secret only for the same existing provider key."""
from contextlib import redirect_stdout, redirect_stderr
import json
import os
from pathlib import Path

from admin_owner55_ai import DiscardedOutput, source_proof
from adopt_supplied_owner55_ai import API, inventory
import provision_owner55_ai as provision
from owner_ai_admin_transport import require_admin_guard, transport_admin

FIELDS = ('configuration_changed','service_restarted','key_matches_supplied',
          'gateway_verified','configuration_loaded','health_verified',
          'auth_boundary_verified','public_feed_unchanged','other_settings_preserved')


def operation_source():
    root=Path(__file__).resolve().parents[1]
    stage=(root/'deploy/stage_owner55_ai.py').read_text()
    active=(root/'deploy/activate_owner55_ai.py').read_text()
    operation=(root/'deploy/sync_owner55_ai_key.py').read_text()
    return ('support={"__name__":"sync_stage"}\nexec(compile('+repr(stage)+',"stage","exec"),support)\n'
        'active={"__name__":"sync_active","STAGING":support}\nexec(compile('+repr(active)+',"active","exec"),active)\n'
        'exec(compile('+repr(operation)+',"key-sync","exec"),'
        '{"STAGING":support,"ACTIVATION":active,"ENVELOPE":ENVELOPE,"__name__":"__main__"})\n')


def synchronize(api, transfer, sources, secret, expected_key_id):
    provision.require_gateway_key(secret)
    if provision.uuid_text(expected_key_id) != expected_key_id or not expected_key_id:
        raise RuntimeError('reviewed_key_identity_required')
    finances=api.request('GET',provision.FINANCES).get('finances')
    if not isinstance(finances,dict) or finances.get('currency') != 'RUB':
        raise RuntimeError('rub_limits_required')
    key_id, identities=inventory(api,expected_key_id)
    if set(identities) != {'day','month'}:
        raise RuntimeError('both_existing_limits_required')
    contract={k:bool for k in FIELDS}
    contract.update(status={'blocked','already_current','synchronized'},server_id=int,
        phase={'identity','configuration','gateway','write','restart','verification','complete'})
    receipt=transfer(operation_source(),{'source_sha256':sources,'key_id':key_id,'limit_ids':identities},
                     secret,contract)
    # Read only; never reset provider spending counters.
    if inventory(api,expected_key_id) != (key_id,identities):
        raise RuntimeError('provider_limits_changed_during_sync')
    return {**receipt,'provider_limits_unchanged':True,'inference_called':False,
            'brokerage_request_sent':False,'provider_daily_cap_rub':'100','provider_monthly_cap_rub':'2900'}


def main():
    receipt={'status':'blocked','phase':'administration'}
    try:
        with redirect_stdout(DiscardedOutput()),redirect_stderr(DiscardedOutput()):
            require_admin_guard()
            receipt=synchronize(API(os.environ['TIMEWEB_CLOUD_TOKEN']),transport_admin,
                source_proof(os.environ),os.environ['TIMEWEB_AI_TOKEN'],
                os.environ['OWNER_SUPPLIED_AI_KEY_ID'])
    except BaseException:
        pass
    finally:
        os.environ.pop('TIMEWEB_AI_TOKEN',None)
        os.environ.pop('TIMEWEB_CLOUD_TOKEN',None)
    print('OWNER_AI_KEY_SYNC='+json.dumps(receipt,sort_keys=True),flush=True)
    raise SystemExit(0 if receipt['status'] in {'synchronized','already_current'} else 1)


if __name__ == '__main__':
    main()
