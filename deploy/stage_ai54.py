"""Stage a dedicated key on the existing runtime; activation is a separate step."""
import json
import os
from pathlib import Path
import re


def main():
    if os.getuid() != 0 or not Path('/etc/analyst-ai/backend.env').is_file():
        raise RuntimeError('existing_owner_runtime_required')
    value = ENVELOPE['payload']
    if (value.get('model') != 'dashscope/qwen3.5-flash' or value.get('daily_rub') != '2'
            or value.get('monthly_rub') != '30' or value.get('fallback_models') != []
            or value.get('smoke',{}).get('synthetic_facts_passed') is not True
            or not re.fullmatch(r'[A-Za-z0-9_./+:-]{16,512}', value.get('token',''))):
        raise RuntimeError('staging_contract_invalid')
    target=Path('/etc/analyst-ai/ai54.json')
    with target.open('x', encoding='utf-8') as output:
        os.chmod(target,0o600)
        output.write(json.dumps(value))
    print('AI54_STAGED='+json.dumps({'model':value['model'],'daily_rub':'2','monthly_rub':'30','key_stored':True,'runtime_enabled':False}),flush=True)


if __name__=='__main__':
    main()
