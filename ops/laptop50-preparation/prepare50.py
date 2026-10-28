"""Administrative text preparation; application compilation and tests run only on the owner laptop."""
from pathlib import Path
import ast
import base64
import hashlib
import json
import re
import zlib
import yaml

ROOT = Path(__file__).resolve().parent
BASE = '5e35c9a7c7ee3aa402f264ce312f59c121617ddc'
OLD_BASE = '6d037bcbba376d2b2e6e53caa0f96874ac1497ef'
OLD_SOURCE = '26d1ccf6b9685925291edb968f17ef091b145831d7c6ca791e5e942246af49fa'
PREFIX = 'ops/laptop50-preparation'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def encoded(value):
    return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()


def replace_once(text, old, new):
    assert text.count(old)==1, old
    return text.replace(old,new,1)


def stage(name,raw):
    b64=base64.b64encode(zlib.compress(raw,9)).decode()
    lines=[]
    for offset in range(0,len(b64),6000):
        mode='w' if offset==0 else 'a'
        lines.append(f'''py -3 -c "from pathlib import Path; import os; p=Path(os.environ['PATCH_DIR'])/{name+'.b64'!r}; p.open({mode!r},encoding='ascii').write({b64[offset:offset+6000]!r})"''')
        lines.append('if errorlevel 1 exit /b 1')
    lines.append(f'''py -3 -c "from pathlib import Path; import os,zlib,base64,hashlib; p=Path(os.environ['PATCH_DIR']); b=zlib.decompress(base64.b64decode((p/{name+'.b64'!r}).read_text())); assert hashlib.sha256(b).hexdigest()=={sha(raw)!r}; (p/{name!r}).write_bytes(b)"''')
    lines.append('if errorlevel 1 exit /b 1')
    return '\n'.join(lines)


def main():
    meta=json.loads((ROOT/'reference/git-inventories.json').read_bytes())
    old=json.loads((ROOT/'reference/admin/source49-final.json').read_bytes())
    assert old['source_sha256']=='8e4dc044ec6b700469a597cf8fc3a23aae96e57e5b5413e378dbf3986e2cef60'
    previous={row['path']:row for row in meta['source49']['tree'] if row['type']=='blob'}
    current={row['path']:row for row in meta['runtime']['tree'] if row['type']=='blob'}
    code={}
    for name,row in current.items():
        if name in ('AGENTS.md','README.md') or name.startswith('docs/'):continue
        if name in previous and previous[name]['sha']==row['sha']:
            code[name]=old['files'][name]
            assert code[name]['bytes']==row['size']
        else:
            raw=(ROOT/'reference/source'/name).read_bytes()
            assert blob(raw)==row['sha'] and len(raw)==row['size'],name
            code[name]={'bytes':len(raw),'sha256':sha(raw)}
    h=hashlib.sha256()
    for name,row in sorted(code.items(),key=lambda item:item[0].encode()):
        h.update(name.encode()+b'\0'+row['sha256'].encode()+b'\0')
    source=h.hexdigest()
    candidate=ROOT/'candidate50/source'
    for name in ('app/build.gradle.kts','.github/scripts/tests/test_android17_live_spectrum.py',
                 '.github/scripts/tests/test_spectrum_brand_identity.py'):
        text=(ROOT/'reference/source'/name).read_text()
        text=replace_once(text,'versionName = "0.14.2"','versionName = "0.15.0"')
        text=replace_once(text,'int(version.group(1)), 49','int(version.group(1)), 50') if name.endswith('test_spectrum_brand_identity.py') else replace_once(text,'versionCode = 49','versionCode = 50')
        path=candidate/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    name='app/src/main/java/ru/omnicio/app/ui/home/HomeScreen.kt'
    text=(ROOT/'reference/source'/name).read_text()
    text=replace_once(text,'                item(key = "automation-state") {',
        '                item(key = "data-readiness") { HomeSystemReadiness(selectedCurrency) }\n                item(key = "automation-state") {')
    (candidate/name).write_text(text)
    rows=[]
    for path in sorted(candidate.rglob('*')):
        if not path.is_file():continue
        name=path.relative_to(candidate).as_posix();raw=path.read_bytes()
        assert b'\r' not in raw and b'\0' not in raw
        old_path=ROOT/'reference/source'/name
        before=old_path.read_bytes() if name in current else None
        if before is not None:
            assert blob(before)==current[name]['sha'] and code[name]=={'bytes':len(before),'sha256':sha(before)}
            assert before!=raw
        if name.endswith('.py'):ast.parse(raw)
        rows.append({'path':name,'old_git_blob':blob(before) if before is not None else None,
            'old_bytes':len(before) if before is not None else None,'old_sha256':sha(before) if before is not None else None,
            'new_bytes':len(raw),'new_sha256':sha(raw),'content':raw.decode()})
    assert len(rows)==7
    reviewed={'schema':1,'kind':'laptop50_integrated_android_source','base_commit':BASE,'base_source_sha256':source,
        'version_before':{'code':49,'name':'0.14.2'},'version_after':{'code':50,'name':'0.15.0'},
        'application_or_tests_executed':False,'files':rows}
    review=encoded(reviewed)
    bundle=json.dumps({'reference_commit':BASE,'files':rows},ensure_ascii=True,separators=(',',':')).encode()
    transport=base64.b64encode(zlib.compress(bundle,9));name='n00-integrated-apk50'
    specification={'name':name,'transport_sha256':sha(transport),'decoded_sha256':sha(bundle)}
    manifest=json.dumps({'schema':1,'base_commit':BASE,'bundles':[specification]},separators=(',',':')).encode()
    bootstrap=(ROOT/'reference/admin/windows-full-development.py').read_bytes()
    assert sha(bootstrap)=='80517ea1faf16cfa1759691321b5ed7dacf95cb94b1f46254eb674faf162f87f'
    bootstrap=replace_once(replace_once(bootstrap.decode(),f'BASE_COMMIT = "{OLD_BASE}"',f'BASE_COMMIT = "{BASE}"'),
        f'BASE_SOURCE = "{OLD_SOURCE}"',f'BASE_SOURCE = "{source}"').encode()
    ast.parse(bootstrap)
    guest=(ROOT/'reference/admin/n00-linux-guest.py').read_bytes()
    assert sha(guest)=='9c92c16d88a9e69a6e9b73b61f0e1eff8cd6b1b457451ee104c07bd17a7e29f0'
    workflow=yaml.safe_load((ROOT/'reference/admin/windows-development.yml').read_bytes())
    assert set(workflow['jobs'])=={'preflight','develop','collect','cleanup','result'}
    workflow['name']='Build integrated APK50 on owner laptop and preserve it on Timeweb'
    develop=workflow['jobs']['develop'];develop['name']='Build and verify the complete latest Android50 application on the owner laptop'
    steps=develop['steps']
    checkout=next(s for s in steps if s.get('name')=='Checkout the exact base source with LF bytes')
    assert checkout['with']['ref']==OLD_BASE;checkout['with']['ref']=BASE
    event=next(s for s in steps if s.get('name')=='Checkout exact event-owned reviewed transport files')
    event['with']['path']='reviewed-apk50-${{ github.run_id }}-${{ github.run_attempt }}'
    event['with']['sparse-checkout']=PREFIX
    changed=[]
    for step in steps:
        label=step.get('name','')
        if label=='Stage verified administrative transport: windows-full-development.py':
            step['run']=stage('windows-full-development.py',bootstrap);changed.append('bootstrap')
        elif label=='Stage verified administrative transport: patch-manifest.json':
            step['run']=stage('patch-manifest.json',manifest);changed.append('manifest')
        elif label=='Stage verified administrative transport: n00-calendar-dispatch49.b64':
            code_text=step['run'].replace('reviewed-calendar49-','reviewed-apk50-').replace('ops/calendar-dispatch49-preparation',PREFIX).replace('n00-calendar-dispatch49',name)
            code_text=replace_once(code_text,'608d4b88a5486e808deb0a1db6a1397172d9ba86e0c014caef4cc715f58194d3',sha(transport))
            ast.parse(code_text);step['run']=code_text;step['name']='Stage verified administrative transport: '+name+'.b64';changed.append('transport')
        elif step.get('uses','').startswith('actions/upload-artifact@'):
            assert step['with']['name']=='n00-candidate49-build-checks';step['with']['name']='n00-candidate50-build-checks';changed.append('artifact')
    assert sorted(changed)==['artifact','bootstrap','manifest','transport']
    raw_workflow=yaml.safe_dump(workflow,allow_unicode=True,sort_keys=False,width=120).encode()
    assert yaml.safe_load(raw_workflow)==workflow and b"'on':" in raw_workflow
    out=ROOT/'candidate50/transport';assert not out.exists();out.mkdir()
    summary={'schema':1,'state':'prepared_source_only','base_commit':BASE,'base_source_sha256':source,
        'base_code_files':len(code),'source_paths':len(rows),'version_code':50,'version_name':'0.15.0-preview',
        'reviewed_files_sha256':sha(review),'bundle_sha256':sha(bundle),'transport_sha256':sha(transport),
        'patch_manifest_sha256':sha(manifest),'bootstrap_sha256':sha(bootstrap),'workflow_sha256':sha(raw_workflow),
        'guest_sha256':sha(guest),'all_original_build_phases_preserved':True,'application_or_tests_executed':False,
        'published':False,'full_plan_complete':False}
    files={'reviewed-files.json':review,'manifest-summary.json':encoded(summary),'patch-manifest.json':manifest,
        name+'.b64':transport,'windows-full-development.py':bootstrap,'n00-linux-guest.py':guest,
        'workflow.yml':raw_workflow,'base-code-inventory.json':encoded(code)}
    for name,raw in files.items():(out/name).write_bytes(raw)
    print(json.dumps(summary))


if __name__=='__main__':main()
