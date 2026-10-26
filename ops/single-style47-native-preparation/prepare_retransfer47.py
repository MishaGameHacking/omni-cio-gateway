"""Repackage verified retained Windows files after a failed private transport.

Administrative file handling only: no app imports, builds, or test execution.
Original build and failed transport receipts remain unchanged.
"""
from pathlib import Path
import ast
import base64
import copy
import hashlib
import json
import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'context/retransfer47-v20'
TARGET = '.github/workflows/retransfer-preview47.yml'

WINDOWS = r'''
import base64, datetime, hashlib, io, json, os, pathlib, stat, sys, zipfile
assert sys.platform == 'win32' and os.environ['COMPUTERNAME'] == 'LAPTOP-NPSGA016'
sha = lambda raw: hashlib.sha256(raw).hexdigest()
raw = base64.b64decode(ORIGINAL_ARTIFACT_B64, validate=True)
assert len(raw) == 248574 and sha(raw) == '806b87abe941d78e798348bdf1b41247530e193eab8f29380a46810565696868'
evidence = {}
with zipfile.ZipFile(io.BytesIO(raw)) as archive:
    for member in archive.infolist():
        path = pathlib.PurePosixPath(member.filename)
        assert not path.is_absolute() and '..' not in path.parts and not member.is_dir()
        assert path.name not in evidence and 0 <= member.file_size < 8000000
        evidence[path.name] = archive.read(member)
build = json.loads(evidence['windows-development.json'])
inventory = json.loads(evidence['source-final.json'])
controller = json.loads(evidence['controller.json'])
original_export = json.loads(evidence['export-receipt.json'])
assert sha(evidence['windows-development.json']) == 'd8f681a58a6b1574f16f284ac514c13a1b942e4683b5de66306a5728b498276f'
assert sha(evidence['source-final.json']) == '683c97da2fad6395fc3b1ce50a9c43386eececc5b072b3bff4f2df665e7a234e'
assert sha(evidence['controller.json']) == '6b2ee57854782e3d4bf227f9519d84316ab511a5922606660ad7cc04c1f241a4'
assert build['github']['run_id'] == 40392908825 and build['status'] == 'passed_check_and_build_only'
root = pathlib.Path(build['root'])
assert root == pathlib.Path('C:/actions-runner-3/_work/omni-cio-gateway/omni-cio-gateway/windows-development-40392908825-1')
def read(path):
    assert path.resolve(strict=True) == path and path.is_file() and not path.is_symlink()
    assert stat.S_ISREG(path.stat().st_mode) and path.stat().st_size <= 128 * 1024**2
    return path.read_bytes()
entries = {}
def add(name, data):
    assert name not in entries
    entries[name] = data
for name, identity in inventory['files'].items():
    relative = pathlib.PurePosixPath(name)
    assert not relative.is_absolute() and '..' not in relative.parts and ':' not in name and '\\' not in name
    data = read(root / name)
    assert {'bytes': len(data), 'sha256': sha(data)} == identity, name
    add('source/' + name, data)
for name, data in evidence.items():
    add('evidence/' + ('original-export-receipt.json' if name == 'export-receipt.json' else name), data)
for name, identity in build['apks'].items():
    data = read(root / name)
    assert {'bytes': len(data), 'sha256': sha(data)} == identity, name
    add('outputs/' + name, data)
for name in ('signature.txt', 'alignment.txt', 'badging.txt', 'manifest.txt', 'apk-verification.json', 'native-alignment.json'):
    relative = 'app/build/outputs/apk/preview/' + name
    add('outputs/' + relative, read(root / relative))
recovery = {'schema': 1, 'kind': 'verified_retained_build_reexport',
    'build_run_id': 40392908825, 'transport_run_id': int(os.environ['GITHUB_RUN_ID']),
    'original_failed_collector_job': 121827044250, 'original_export': original_export,
    'all_original_source_files_and_apks_reverified': True,
    'original_build_receipts_unchanged': True, 'new_build_or_tests_executed': False,
    'original_archive_byte_identity_claimed': False,
    'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
add('evidence/reexport-provenance.json', (json.dumps(recovery, sort_keys=True) + '\n').encode())
envelope = {'schema': 1, 'kind': 'windows_check_build_source_archive',
    'source_sha256': inventory['source_sha256'], 'complete_source_sha256': inventory['complete_source_sha256'],
    'base_commit': build['base_commit'], 'report': build, 'controller': controller,
    'files': {name: {'bytes': len(data), 'sha256': sha(data)} for name, data in entries.items()},
    'runtime_pass': False, 'publication_authorized': False, 'phone_verified': False,
    'created_at': recovery['created_at'], 'reexport': recovery}
destination = pathlib.Path(os.environ['RUNNER_TEMP']) / 'ci-handoff.zip'
assert not destination.exists()
with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
    for name, data in sorted(entries.items()):
        archive.writestr(name, data)
    archive.writestr('windows-development-envelope.json', json.dumps(envelope, sort_keys=True))
for name, identity in inventory['files'].items():
    data = read(root / name)
    assert {'bytes': len(data), 'sha256': sha(data)} == identity, name
data = read(destination)
assert len(data) < 256 * 1024**2
receipt = {'bytes': len(data), 'sha256': sha(data), 'files': len(entries),
    'source_sha256': inventory['source_sha256'], 'complete_source_sha256': inventory['complete_source_sha256'],
    'status': build['status'], 'runtime_pass': False, 'publication_authorized': False,
    'reexport': recovery}
folder = pathlib.Path(os.environ['RUNNER_TEMP']) / 'retransfer47-receipts'
folder.mkdir()
(folder/'export-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
(folder/'reexport-provenance.json').write_text(json.dumps(recovery, indent=2)+'\n', encoding='utf-8')
print('VERIFIED_REEXPORT47=' + json.dumps(receipt))
'''

def main():
    assert not OUT.exists()
    artifact = (ROOT/'context/build47-v20/original-artifact.zip').read_bytes()
    assert hashlib.sha256(artifact).hexdigest() == '806b87abe941d78e798348bdf1b41247530e193eab8f29380a46810565696868'
    windows = 'ORIGINAL_ARTIFACT_B64 = ' + repr(base64.b64encode(artifact).decode()) + '\n' + WINDOWS
    ast.parse(windows)
    w = copy.deepcopy(yaml.safe_load((ROOT/'context/candidate47-autosave-v20/workflow.yml').read_text()))
    w['name'] = 'Return exact retained preview47 to Timeweb without rebuilding'
    w['on']['push']['paths'] = [TARGET]
    w['concurrency'] = {'group': 'preview47-retained-retransfer', 'cancel-in-progress': False}
    develop = w['jobs']['develop']
    old_steps = develop['steps']
    keep = [copy.deepcopy(s) for s in old_steps if s.get('id') in ('evidence_prepare', 'evidence_upload')]
    assert len(keep) == 2
    keep[0].pop('if', None)
    develop['name'] = 'Reverify and repackage retained laptop source and APK bytes'
    develop['timeout-minutes'] = 12
    develop['env'] = {'SOURCE_ROOT': 'C:/actions-runner-3/_work/omni-cio-gateway/omni-cio-gateway/windows-development-40392908825-1',
        'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8', 'PYTHONUNBUFFERED': '1'}
    develop['steps'] = [{'name': 'Read exact retained files and original successful receipts',
        'id': 'export', 'shell': 'py -3 {0}', 'run': windows}, *keep,
        {'name': 'Preserve actual reexport identities', 'if': 'always()',
         'uses': 'actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9',
         'with': {'name': 'preview47-reexport-receipts', 'path': '${{ runner.temp }}/retransfer47-receipts/',
                  'retention-days': 3, 'if-no-files-found': 'error'}}]
    step = w['jobs']['collect']['steps'][-1]
    old = 'run=os.environ["GITHUB_RUN_ID"];attempt=os.environ["GITHUB_RUN_ATTEMPT"]'
    assert step['run'].count(old) == 1
    step['run'] = step['run'].replace(old, 'run="40392908825";attempt="1" # Original build identity; current run only transports its verified files')
    w['jobs']['result']['name'] = 'Require exact retained bytes returned and private transfer removed'
    OUT.mkdir()
    raw = yaml.safe_dump(w, allow_unicode=True, sort_keys=False, width=120)
    assert yaml.safe_load(raw) == w
    (OUT/'workflow.yml').write_text(raw)
    (OUT/'windows-reexport.py').write_text(windows)
    print(json.dumps({'workflow': str(OUT/'workflow.yml'), 'characters': len(raw),
        'sha256': hashlib.sha256(raw.encode()).hexdigest(), 'no_build_or_test_execution': True}))

if __name__ == '__main__':
    main()
