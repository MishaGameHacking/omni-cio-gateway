"""Prepare reviewed release administration; does not import or execute application code."""
import ast
import hashlib
import json
from pathlib import Path
import re
import yaml

ROOT = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def literal(value):
    return ast.parse(repr(value), mode='eval').body


def main():
    cfg = json.loads((ROOT/'candidate50/publication-config.json').read_bytes())
    evidence = ROOT/cfg['evidence_directory']
    build_raw = (evidence/'windows-development.json').read_bytes()
    export_raw = (evidence/'export-receipt.json').read_bytes()
    inventory_raw = (evidence/'source-final.json').read_bytes()
    build, export, inventory = map(json.loads, (build_raw, export_raw, inventory_raw))
    assert build['status'] == 'passed_check_and_build_only'
    assert build['check']['status'] == build['build']['status'] == 'passed'
    assert build['github']['run_id'] == cfg['run_id'] and build['github']['run_attempt'] == 1
    assert build['source_sha256'] == build['source_sha256_after'] == inventory['source_sha256']
    assert build['check']['source_sha256'] == build['build']['source_sha256'] == inventory['source_sha256']
    apk = build['apks']['app/build/outputs/apk/preview/app-preview.apk']
    assert build['build']['apk_sha256'] == apk['sha256']
    assert build['certificate_sha256'] == 'bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1'
    assert export['status'] == 'passed_check_and_build_only' and export['source_sha256'] == inventory['source_sha256']
    assert export['runtime_pass'] is False and export['publication_authorized'] is False
    baseline = (ROOT/'reference/publication/owner-preview49-public-verification.json').read_bytes()
    observation = (ROOT/'evidence/runtime-source79/receipt.txt').read_bytes()
    observation_json = json.loads(observation)
    assert observation_json['all_backend_sources_match_candidate_base'] is True
    runtime = {name.removeprefix('backend/'): item for name,item in inventory['files'].items()
               if name.startswith('backend/') and name.count('/') == 1 and name.endswith('.py')}
    assert len(runtime) == 79
    for name,item in runtime.items():
        observed = observation_json['backend_source_inventory'][name]
        assert observed['matches_candidate_base'] is True
        assert item == {k: observed[k] for k in ('bytes','sha256')}
    old_apk = '9940c994d3e6695708fe65d64e378c6d998c8891ae69bbaa1c20df17008dbb6e'
    strings = {
        old_apk: apk['sha256'],
        '85fb8b3c3e0020080a421efaae1c101df0e55f97bacb791064e1b1cbaa4a8df1': old_apk,
        'dc171704ffcf004aad7d8990408d301e9b3a63b6f030c0a5321e776cb7711fe4': export['sha256'],
        '8e4dc044ec6b700469a597cf8fc3a23aae96e57e5b5413e378dbf3986e2cef60': inventory['source_sha256'],
        '521d96293a048e4254bec936710bcfbf166b20a0': cfg['source_backup_commit'],
        '7af8b02af5070253d69b38734372f59d5f47e40961300122aca6e904a89459f0': sha(build_raw),
        '0640ce9ae4333816b08e2f025d3b0dd678e8ac6abaa4ae2241cc9df9389f278e': sha(export_raw),
        '24cfc7637f14c922ac4d366feea9b1fd9dc50a99fd85dc822356aefc4b065cf2': sha(baseline),
        '2920c8a03991d5c1792d64a10e05f92cea323f58791ab40732e1d6acbbf21782': sha(observation),
        '0.14.2-preview': '0.15.0-preview', '0.14.1-preview': '0.14.2-preview',
        '2026-10-27': '2026-10-28',
    }
    fragments = {'preview49':'preview50', 'PREVIEW49':'PREVIEW50', 'exact49':'exact50',
                 'exact48':'exact49', 'Analyst-AI-49-':'Analyst-AI-50-',
                 '40453334023':str(cfg['run_id']), 'calendar_runtime':'runtime_source'}
    pattern = re.compile('|'.join(map(re.escape,fragments)))

    class Adapt(ast.NodeTransformer):
        def visit_Constant(self, node):
            if type(node.value) is str:
                value = strings.get(node.value, node.value)
                value = pattern.sub(lambda m: fragments[m.group()],value)
                return ast.copy_location(ast.Constant(value),node)
            if type(node.value) is int:
                return ast.copy_location(ast.Constant({49:50,48:49,29937843:apk['bytes'],
                    69716504:export['bytes'],40453334023:cfg['run_id']}.get(node.value,node.value)),node)
            return node

        def visit_Name(self,node):
            node.id = pattern.sub(lambda m: fragments[m.group()],node.id)
            return node

        def visit_keyword(self,node):
            self.generic_visit(node)
            if node.arg: node.arg = pattern.sub(lambda m: fragments[m.group()],node.arg)
            return node

        def visit_Assign(self,node):
            self.generic_visit(node)
            name = node.targets[0].id if len(node.targets)==1 and isinstance(node.targets[0],ast.Name) else None
            if name == 'OLD_BYTES': node.value = literal(29937843)
            if name == 'required_runtime': node.value = literal(runtime)
            if name == 'notes': node.value = literal('Версия 0.15.0-preview. На главной виден номер установленной сборки. Панель данных показывает свежесть оценки портфеля, событий и источников, а также ограничения анализа. Единый стиль и существующее автосохранение сохранены. Торговля выключена; нативная приёмка остаётся открытой.')
            if name == 'authorization':
                value = ast.literal_eval(node.value)
                value['runtime_source_sources'] = runtime
                value['owner_request'] = 'Получить и собрать APK на компьютере, обновить сам APK в существующем рабочем канале Timeweb; промежуточная публикация без повторной полной native-матрицы ранее разрешена.'
                value['reason_for_current_manifest_change'] = 'Owner requests the actual updated APK. Exact laptop build, original signing identity, prior release and all 79 current backend source files are verified. Native and phone acceptance remain open.'
                value['windows_workflow_sha'] = cfg['workflow_sha']
                value['all_five_workflow_jobs_passed'] = True
                value['source_inventory_sha256'] = sha(inventory_raw)
                node.value = literal(value)
            return node

    template = ROOT/'reference/publication'
    publisher = ast.unparse(ast.fix_missing_locations(Adapt().visit(ast.parse((template/'publish-preview49.py').read_text()))))+'\n'
    verifier = ast.unparse(ast.fix_missing_locations(Adapt().visit(ast.parse((template/'verify-public49.py').read_text()))))+'\n'
    # Keep the original pinned host/credential/SSH cleanup implementation byte-for-byte.
    old_hosted = (template/'hosted-delivery.py').read_text()
    remote_node = next(n for n in ast.parse(old_hosted).body if isinstance(n,ast.Assign)
                       and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='remote')
    prefix = ''.join(old_hosted.splitlines(keepends=True)[:remote_node.lineno-1])
    remote = "import subprocess\nresult=subprocess.run(['/opt/analyst-ai/venv/bin/python','-c',"+repr(publisher)+"],stdin=subprocess.DEVNULL,timeout=180)\nraise SystemExit(result.returncode)\n"
    hosted = prefix+'remote = '+repr(remote)+'\n'+verifier
    ast.parse(publisher);ast.parse(verifier);ast.parse(hosted)
    assert '49' not in re.sub('[0-9a-f]{40,64}','',publisher.split('notes =',1)[1].split('authorization =',1)[0])
    checker = '''import hashlib,json,os,pathlib,subprocess,urllib.request
cfg = json.loads(pathlib.Path('.publication-input/ops/apk50-publication/publication-config.json').read_bytes())
expected_raw = pathlib.Path('.publication-input/ops/apk50-publication/source-final.json').read_bytes()
assert hashlib.sha256(expected_raw).hexdigest() == cfg['source_inventory_sha256']
inventory = json.loads(expected_raw)
root = pathlib.Path('source-backup50').resolve(strict=True)
assert subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip() == cfg['source_backup_commit']
names = subprocess.check_output(['git','-C',str(root),'ls-files','-z']).decode().split('\\0')
names = sorted((n for n in names if n and n not in ('AGENTS.md','README.md') and not n.startswith('docs/')),key=lambda x:x.encode())
expected_code = {n for n in inventory['files'] if n not in ('AGENTS.md','README.md') and not n.startswith('docs/')}
assert set(names) == expected_code
digest = hashlib.sha256()
for name in names:
    path = root/name
    assert path.is_file() and not path.is_symlink() and path.resolve(strict=True).is_relative_to(root)
    data = path.read_bytes();identity = {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    assert identity == inventory['files'][name],name
    digest.update(name.encode()+b'\\0'+identity['sha256'].encode()+b'\\0')
assert digest.hexdigest() == inventory['source_sha256'] == cfg['source_sha256']
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl): return None
opener=urllib.request.build_opener(NoRedirect())
def read(path):
    req=urllib.request.Request('https://api.github.com/repos/MishaGameHacking/omni-cio-gateway'+path,headers={'Authorization':'Bearer '+os.environ['GH_READ_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
    with opener.open(req,timeout=45) as response:
        assert response.status==200
        raw=response.read(2*1024**2+1);assert len(raw)<=2*1024**2
        return json.loads(raw)
run=read('/actions/runs/'+str(cfg['run_id']))
assert run['head_sha']==cfg['workflow_sha'] and run['run_attempt']==1
assert run['status']=='completed' and run['conclusion']=='success'
assert run['path']=='.github/workflows/windows-development.yml'
assert run['head_branch']=='codex/timeweb-owner-prepare-2026-10-23'
jobs=read('/actions/runs/'+str(cfg['run_id'])+'/attempts/1/jobs?per_page=100')
assert jobs['total_count']==len(jobs['jobs'])==5
assert all(j['status']=='completed' and j['conclusion']=='success' and j['head_sha']==cfg['workflow_sha'] for j in jobs['jobs'])
assert sorted(j['name'] for j in jobs['jobs'])==sorted(cfg['job_names'])
print(json.dumps({'source_backup_verified':True,'code_files':len(names),'source_sha256':digest.hexdigest(),'run_id':cfg['run_id'],'all_five_jobs_passed':True}))
'''
    ast.parse(checker)
    workflow = yaml.safe_load((template/'deliver-preview49.yml').read_text())
    workflow['name'] = 'Publish actual laptop-built APK50 to existing Timeweb channel'
    workflow['on']['push']['paths'] = ['.github/workflows/deliver-preview50.yml']
    workflow['permissions']['actions'] = 'read'
    steps = workflow['jobs']['deliver']['steps']
    checkout = steps[0]['uses']
    steps[1:1] = [
        {'name':'Checkout exact tested source backup for byte comparison','uses':checkout,
         'with':{'ref':cfg['source_backup_commit'],'path':'source-backup50','persist-credentials':False}},
        {'name':'Checkout current event publication evidence only','uses':checkout,
         'with':{'ref':'${{ github.sha }}','path':'.publication-input','persist-credentials':False,
                 'sparse-checkout':'ops/apk50-publication','sparse-checkout-cone-mode':False}},
        {'name':'Verify all source bytes and the five completed owner laptop jobs',
         'env':{'GH_READ_TOKEN':'${{ github.token }}'},'run':"python3 - <<'PY'\n"+checker+"PY\n"}]
    steps[4]['name'] = 'Publish exact APK50 and verify public policy, entire APK and backend health'
    steps[4]['run'] = "python3 - <<'PY'\n"+hosted+"PY\n"
    steps[5]['with']['name'] = 'owner-preview50-public-verification-${{ github.run_id }}-${{ github.run_attempt }}'
    steps[5]['with']['path'] = '${{ runner.temp }}/owner-preview50-public-verification.json'
    cfg.update(source_inventory_sha256=sha(inventory_raw),source_sha256=inventory['source_sha256'])
    out=ROOT/'candidate50/publication';assert not out.exists();out.mkdir()
    files={'publish-preview50.py':publisher,'verify-public50.py':verifier,'hosted-delivery.py':hosted,
           'verify-source-and-build.py':checker,'source-final.json':inventory_raw.decode(),
           'publication-config.json':json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',
           'workflow.yml':yaml.safe_dump(workflow,allow_unicode=True,sort_keys=False,width=120)}
    for name,text in files.items(): (out/name).write_text(text)
    print(json.dumps({'run_id':cfg['run_id'],'source_backup_commit':cfg['source_backup_commit'],
        'apk':apk,'archive':{'bytes':export['bytes'],'sha256':export['sha256']},
        'publication_prepared_only':True,'files':{n:sha(t.encode()) for n,t in files.items()}},ensure_ascii=False))


if __name__=='__main__': main()
