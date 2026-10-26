"""Move reviewed transport bytes out of YAML; keep exact hash checks on Windows."""
from pathlib import Path
import ast
import argparse
import hashlib
import json
import shutil
import yaml

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--source',default='candidate48-mandate-v2')
parser.add_argument('--output',default='candidate48-mandate-v3')
args=parser.parse_args()
SOURCE=ROOT/'context'/args.source
OUT=ROOT/'context'/args.output
assert SOURCE.parent==OUT.parent==ROOT/'context'
assert not OUT.exists()
shutil.copytree(SOURCE,OUT)
w=yaml.safe_load((OUT/'workflow.yml').read_text())
steps=w['jobs']['develop']['steps']
index=next(i for i,s in enumerate(steps) if s.get('name')=='Create isolated transport folder')+1
steps.insert(index,{'name':'Checkout exact event-owned reviewed transport files',
    'uses':'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1',
    'with':{'ref':'${{ github.sha }}','path':'reviewed-mandate48-${{ github.run_id }}-${{ github.run_attempt }}',
            'persist-credentials':False,'sparse-checkout':'ops/portfolio-mandate48-preparation','sparse-checkout-cone-mode':False}})
summary=json.loads((OUT/'manifest-summary.json').read_text())
for spec in summary['bundle_specs']:
    name=spec['name']+'.b64'
    expected=spec['transport_sha256']
    assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==expected
    step=next(s for s in steps if s.get('name')=='Stage verified administrative transport: '+name)
    code=f'''import hashlib, os, pathlib, stat, sys
assert sys.platform == 'win32' and os.environ['COMPUTERNAME'] == 'LAPTOP-NPSGA016'
base=pathlib.Path(os.environ['GITHUB_WORKSPACE'])
source=base/('reviewed-mandate48-'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT'])/'ops/portfolio-mandate48-preparation'/{name!r}
assert source.resolve(strict=True)==source and source.is_file() and not source.is_symlink()
assert stat.S_ISREG(source.stat().st_mode) and 0<source.stat().st_size<4*1024**2
raw=source.read_bytes()
assert hashlib.sha256(raw).hexdigest()=={expected!r}
target=pathlib.Path(os.environ['PATCH_DIR'])/{name!r}
assert target.parent.resolve(strict=True)==target.parent and target.parent.is_dir()
assert not target.exists()
with target.open('xb') as out:out.write(raw)
assert target.read_bytes()==raw
print('REVIEWED_TRANSPORT_STAGED='+{name!r})
'''
    ast.parse(code)
    step.clear();step.update({'name':'Stage verified administrative transport: '+name,'shell':'py -3 {0}','run':code})
raw=yaml.safe_dump(w,allow_unicode=True,sort_keys=False,width=120)
assert yaml.safe_load(raw)==w and len(raw)<100000
(OUT/'workflow.yml').write_text(raw)
summary['workflow_sha256']=hashlib.sha256(raw.encode()).hexdigest()
summary['transport_storage']='exact GitHub event SHA, per-file SHA256 checked before Windows staging'
summary['superseded_unstarted_workflow_run']=40397424506
(OUT/'manifest-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
entries=[]
for name in ['reviewed-files.json','manifest-summary.json',*[s['name']+'.b64' for s in summary['bundle_specs']]]:
    entries.append({'path':'ops/portfolio-mandate48-preparation/'+name,'mode':'100644','type':'blob','content':(OUT/name).read_text()})
entries.append({'path':'ops/portfolio-mandate48-preparation/prepare_compact_transport48.py','mode':'100644','type':'blob','content':Path(__file__).read_text()})
entries.append({'path':'ops/portfolio-mandate48-preparation/prepare_mandate_ui48.py','mode':'100644','type':'blob','content':(ROOT/'context/design47/prepare_mandate_ui48.py').read_text()})
entries.append({'path':'.github/workflows/windows-development.yml','mode':'100644','type':'blob','content':raw})
encoded=json.dumps(entries,ensure_ascii=False)
(ROOT/'context/mandate48-compact-dispatch.json').write_text(encoded)
print(json.dumps({'workflow_bytes':len(raw),'sha256':summary['workflow_sha256'],'entries':len(entries),'characters':len(encoded)}))
