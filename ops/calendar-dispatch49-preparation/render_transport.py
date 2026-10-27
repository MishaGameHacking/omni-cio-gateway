"""Administrative source-text packaging for the existing Windows/WSL runner."""
from pathlib import Path
import argparse
import ast
import base64
import difflib
import hashlib
import importlib.util
import json
import zlib

import yaml

HERE = Path(__file__).resolve().parent
CONTEXT = HERE.parent
BASE = '6d037bcbba376d2b2e6e53caa0f96874ac1497ef'
SOURCE = '26d1ccf6b9685925291edb968f17ef091b145831d7c6ca791e5e942246af49fa'
PREFIX = 'ops/calendar-dispatch49-preparation'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def jb(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.absolute()
    assert out.parent == CONTEXT and not out.exists()
    inventory_raw = (CONTEXT / 'build48-v7/source-final.json').read_bytes()
    assert sha(inventory_raw) == '17c38232cea887b33a6315f2f4204b4dccbba97b6dbc07a3d12abf632bd16915'
    inventory = json.loads(inventory_raw)
    assert inventory['source_sha256'] == SOURCE
    helper_path = CONTEXT / 'prepare_candidate45.py'
    assert sha(helper_path.read_bytes()) == '69bfb8dbefd2cb3ce7bbf03dbd3bbbaf90c66b8b6fb5d38873a6f27e878ecf9a'
    spec = importlib.util.spec_from_file_location('administrative_build_transport49', helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.verify_transport_source()
    rows, patch = [], []
    for path in sorted((HERE / 'source-text').rglob('*')):
        if not path.is_file():
            continue
        name = path.relative_to(HERE / 'source-text').as_posix()
        assert name.startswith(('backend/', 'app/', '.github/scripts/')) and '__pycache__' not in name
        raw = path.read_bytes()
        assert b'\r' not in raw and len(raw) < 2 * 1024**2
        text = raw.decode()
        old_path = HERE / 'reference' / name
        old = old_path.read_bytes() if old_path.exists() else None
        if old is None:
            assert name not in inventory['files']
        else:
            assert inventory['files'][name] == {'bytes': len(old), 'sha256': sha(old)}
            assert old != raw
        if name.endswith('.py'):
            ast.parse(raw, filename=name)
        rows.append({'path': name, 'old_git_blob': hashlib.sha1(b'blob ' + str(len(old)).encode() + b'\0' + old).hexdigest() if old is not None else None,
            'old_bytes': len(old) if old is not None else None, 'old_sha256': sha(old) if old is not None else None,
            'new_bytes': len(raw), 'new_sha256': sha(raw), 'content': text})
        patch.extend(difflib.unified_diff((old or b'').decode().splitlines(keepends=True), text.splitlines(keepends=True),
                                        fromfile='a/' + name, tofile='b/' + name))
    assert 1 <= len(rows) <= 100 and len({r['path'].casefold() for r in rows}) == len(rows)
    reviewed = {'schema': 1, 'kind': 'calendar_dispatch49_source_text', 'base_commit': BASE, 'base_source_sha256': SOURCE,
                'base_build_run': 40400521138, 'version_before': {'code': 48, 'name': '0.14.1'},
                'version_after': {'code': 49, 'name': '0.14.2'}, 'application_or_tests_executed': False, 'files': rows}
    review_raw = jb(reviewed)
    bundle = json.dumps({'reference_commit': BASE, 'files': rows}, ensure_ascii=True, separators=(',', ':')).encode()
    transport = base64.b64encode(zlib.compress(bundle, 9))
    name = 'n00-calendar-dispatch49'
    bundle_spec = {'name': name, 'transport_sha256': sha(transport), 'decoded_sha256': sha(bundle)}
    manifest = json.dumps({'schema': 1, 'base_commit': BASE, 'bundles': [bundle_spec]}, separators=(',', ':')).encode()
    bootstrap = helper.bootstrap(BASE, SOURCE)
    guest = helper.read_pinned(CONTEXT / 'full-build-baseline/n00-linux-guest.py', helper.BASELINE_GUEST_SHA256)
    workflow = yaml.safe_load(helper.workflow(BASE, bootstrap, guest, transport, manifest))
    workflow['name'] = 'Calendar and durable event dispatch; verify candidate49'
    develop = workflow['jobs']['develop']
    develop['name'] = 'Apply candidate49 on the authorized laptop and complete the full Windows/WSL build'
    steps = develop['steps']
    index = next(i for i, step in enumerate(steps) if step.get('name') == 'Create isolated transport folder') + 1
    steps.insert(index, {'name': 'Checkout exact event-owned reviewed transport files',
        'uses': 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1',
        'with': {'ref': '${{ github.sha }}', 'path': 'reviewed-calendar49-${{ github.run_id }}-${{ github.run_attempt }}',
            'persist-credentials': False, 'sparse-checkout': PREFIX, 'sparse-checkout-cone-mode': False}})
    staged = artifact = 0
    for step in steps:
        if step.get('name') == 'Stage verified administrative transport: n00-native45.b64':
            code = f'''import hashlib, os, pathlib, stat, sys
assert sys.platform == 'win32' and os.environ['COMPUTERNAME'] == 'LAPTOP-NPSGA016'
base = pathlib.Path(os.environ['GITHUB_WORKSPACE'])
source = base / ('reviewed-calendar49-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']) / {PREFIX!r} / {name + '.b64'!r}
assert source.resolve(strict=True) == source and source.is_file() and not source.is_symlink()
assert stat.S_ISREG(source.stat().st_mode) and 0 < source.stat().st_size < 4 * 1024**2
raw = source.read_bytes()
assert hashlib.sha256(raw).hexdigest() == {sha(transport)!r}
target = pathlib.Path(os.environ['PATCH_DIR']) / {name + '.b64'!r}
assert target.parent.resolve(strict=True) == target.parent and target.parent.is_dir()
assert not target.exists()
with target.open('xb') as stream: stream.write(raw)
assert target.read_bytes() == raw
print('REVIEWED_TRANSPORT_STAGED=' + {name + '.b64'!r})
'''
            ast.parse(code)
            step.clear()
            step.update({'name': 'Stage verified administrative transport: ' + name + '.b64', 'shell': 'py -3 {0}', 'run': code})
            staged += 1
        if step.get('uses', '').startswith('actions/upload-artifact@'):
            assert step['with']['name'] == 'n00-candidate45-build-checks'
            step['with']['name'] = 'n00-candidate49-build-checks'
            step['with']['path'] += '\n${{ github.workspace }}/windows-development-${{ github.run_id }}-${{ github.run_attempt }}/app/build/test-results/testDebugUnitTest/*.xml'
            artifact += 1
    assert staged == artifact == 1
    workflow_raw = yaml.safe_dump(workflow, allow_unicode=True, sort_keys=False, width=120).encode()
    assert len(workflow_raw) < 100000 and b'n00-native45' not in workflow_raw
    summary = {'state': 'prepared_source_text_only', 'base_commit': BASE, 'base_source_sha256': SOURCE,
        'base_build_run': 40400521138, 'source_paths': len(rows), 'new_paths': sum(r['old_git_blob'] is None for r in rows),
        'version_code': 49, 'version_name': '0.14.2-preview', 'reviewed_files_sha256': sha(review_raw),
        'bundle_sha256': sha(bundle), 'transport_sha256': sha(transport), 'patch_manifest_sha256': sha(manifest),
        'bootstrap_sha256': sha(bootstrap), 'workflow_sha256': sha(workflow_raw), 'bundle_specs': [bundle_spec],
        'transport_storage': 'exact GitHub event SHA, per-file SHA256 verified on Windows',
        'applied_on_windows': False, 'build_passed': False, 'native_passed': False, 'deployed': False, 'plan_complete': False}
    out.mkdir()
    files = {'reviewed-files.json': review_raw, 'bundle.json': bundle, name + '.b64': transport, 'patch-manifest.json': manifest,
             'windows-full-development.py': bootstrap, 'n00-linux-guest.py': guest, 'workflow.yml': workflow_raw,
             'manifest-summary.json': jb(summary), 'candidate.patch': ''.join(patch).encode()}
    for filename, raw in files.items():
        (out / filename).write_bytes(raw)
    for row in rows:
        path = out / 'source' / row['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(row['content'].encode())
    entries = [{'path': PREFIX + '/' + filename, 'mode': '100644', 'type': 'blob', 'content': files[filename].decode()}
               for filename in ('reviewed-files.json', 'manifest-summary.json', name + '.b64')]
    entries += [{'path': PREFIX + '/' + filename, 'mode': '100644', 'type': 'blob', 'content': (HERE / filename).read_text()}
                for filename in ('render_transport.py', 'prepare_integrations.py')]
    entries.append({'path': '.github/workflows/windows-development.yml', 'mode': '100644', 'type': 'blob', 'content': workflow_raw.decode()})
    (out / 'dispatch-tree.json').write_bytes(jb(entries))
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
