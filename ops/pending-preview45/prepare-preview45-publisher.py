"""Generate a pinned operational publisher only from complete actual native receipts.

This file does not publish, import application code, or run any application test.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import yaml

args = argparse.ArgumentParser()
args.add_argument('--build', type=Path, required=True)
args.add_argument('--native', type=Path, required=True)
args.add_argument('--native-export', type=Path, required=True)
args.add_argument('--native-run', type=int, required=True)
args.add_argument('--source-commit', required=True)
args.add_argument('--base-workflow', type=Path, default=Path('.github/workflows/deliver-preview44.yml'))
options = args.parse_args()
here = Path(__file__).parent
sha = lambda data: hashlib.sha256(data).hexdigest()
report_bytes = (options.build / 'windows-development.json').read_bytes()
report = json.loads(report_bytes)
receipt_bytes = (options.build / 'export-receipt.json').read_bytes()
receipt = json.loads(receipt_bytes)
assert report['status'] == 'passed_check_and_build_only'
assert report['source_sha256'] == report['source_sha256_after'] == receipt['source_sha256']
assert json.loads((options.build / 'controller.json').read_text())['worker_exit_code'] == 0
apk = report['apks']['app/build/outputs/apk/preview/app-preview.apk']
source = report['source_sha256']
native_export = json.loads(options.native_export.read_text())

def native_file(leaf):
    matches = [p for p in options.native.rglob(leaf) if 'ui-screens-api37-16384' not in str(p)]
    assert len(matches) == 1, leaf
    data = matches[0].read_bytes()
    return data, json.loads(data)

summary_raw, summary = native_file('native45-navigation-summary.json')
observed_raw, observed = native_file('navigation-focused-observations.json')
assert summary['navigation']['complete'] is True and observed['navigation_complete'] is True
assert summary['source_commit'] == options.source_commit and summary['source_sha256'] == source
assert observed['error'] == 'Diagnostic only: full UI suite was deliberately not claimed'
assert summary['release_gate_pass'] is False and summary['full15']['accepted'] is False
receipts = {}
for name in ('native45-navigation-summary.json', 'runtime-16384.json', 'install-results.json',
             'navigation-focused-observations.json', 'automation-verification.json',
             'navigation-panels-verification.json', 'navigation-detail-verification.json',
             'navigation-wide-verification.json'):
    raw, _ = native_file(name)
    prefix = 'controller/' if name in ('native45-navigation-summary.json', 'runtime-16384.json') else (
        'install-api37-16384/' if name == 'install-results.json' else 'ui-screens/')
    receipts[prefix + name] = sha(raw)
expected = dict(run_id=options.native_run, archive_bytes=native_export['bytes'],
                archive_sha256=native_export['sha256'], receipts=receipts)
required = {'automation-verification.json': 26, 'navigation-panels-verification.json': 4,
            'navigation-detail-verification.json': 2, 'navigation-wide-verification.json': 2}
native_proof = {**expected, 'run_attempt': 1, 'navigation_cases': required,
    'navigation_complete': True, 'android_api': 37, 'page_size_bytes': 16384,
    'previous44_clean_install': True, 'upgrade44_to45': True, 'candidate45_clean_install': True,
    'upgrade_and_clean_bootstrap_launch': True, 'physical_phone_verified': False,
    'original14_executed': False, 'full_runtime_matrix_passed': False}
old_sha = 'f0af0b45515143f8abb2c28e73d0d484acde5c6a36e18de1b398692bc45a4cf6'
build_run = report['github']['run_id']
tree = ast.parse((here / 'publisher44.py').read_text())
authorization_node = next(n for n in tree.body if isinstance(n, ast.Assign)
    and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'authorization')
authorization = ast.literal_eval(authorization_node.value)
authorization.update(version_code=45, apk_sha256=apk['sha256'], apk_bytes=apk['bytes'],
    source_archive_sha256=receipt['sha256'], source_archive_bytes=receipt['bytes'],
    source_sha256=source, source_backup_commit=options.source_commit,
    build_report_sha256=sha(report_bytes), build_export_receipt_sha256=sha(receipt_bytes),
    windows_run_id=build_run, windows_run_attempt=1, preview_install_smoke=native_proof,
    original14_run_id=options.native_run, original14_status='not_executed_in_navigation_only_run')

class Version(ast.NodeTransformer):
    def visit_Constant(self, node):
        if type(node.value) is int:
            node.value = {43: 44, 44: 45, 40282775349: build_run}.get(node.value, node.value)
        elif type(node.value) is str:
            exact = {'0.13.5-preview': '0.13.6-preview', '0.13.6-preview': '0.13.7-preview',
                '/var/lib/analyst-ai-build/incoming/windows-development-40282775349-1':
                    '/var/lib/analyst-ai-build/incoming/windows-development-' + str(build_run) + '-1'}
            node.value = exact.get(node.value, node.value)
            for before, after in (('preview44', 'preview45'), ('PREVIEW44', 'PREVIEW45'),
                                  ('exact44', 'exact45')):
                node.value = node.value.replace(before, after)
        return node

tree = Version().visit(tree)
constants = dict(APK_SHA=apk['sha256'], APK_BYTES=apk['bytes'], OLD_SHA=old_sha, OLD_BYTES=29771254,
    ARCHIVE_SHA=receipt['sha256'], ARCHIVE_BYTES=receipt['bytes'], SOURCE_SHA=source,
    SOURCE_BACKUP=options.source_commit, BUILD_REPORT_SHA=sha(report_bytes),
    notes='Тестовая версия 0.13.7-preview. Добавлены нижняя и боковая панели разделов, прямые переходы и защита несохранённых изменений. Полная проверка интерфейса продолжается.',
    authorization=authorization)
for node in tree.body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in constants:
        node.value = ast.parse(repr(constants[node.targets[0].id]), mode='eval').body
publisher = ast.unparse(ast.fix_missing_locations(tree)) + '\n'
guard = (here / 'verify-native45-publication.payload').read_text()
anchor = "for path in (pathlib.Path('/opt'), pathlib.Path('/opt/analyst-ai'), pathlib.Path('/opt/analyst-ai/backend')):"
assert publisher.count(anchor) == 1
publisher = publisher.replace(anchor, 'NATIVE_EXPECTED = ' + repr(expected) + '\n' + guard +
    'navigation_proof = verify_native_navigation(NATIVE_EXPECTED)\n\n' + anchor)
anchor = 'candidate = AndroidRelease.parse('
assert publisher.count(anchor) == 1
publisher = publisher.replace(anchor, "need(authorization['preview_install_smoke'] == navigation_proof, 'native_prepublication_proof_conflict')\n" + anchor)
assert publisher.index('verify_native_navigation(NATIVE_EXPECTED)') < publisher.index('with publication_lock(directory):')
ast.parse(publisher)
(here / 'publisher45.py').write_text(publisher)

base = yaml.safe_load(options.base_workflow.read_text())
base['name'] = 'Deliver verified navigation preview45 through the existing owner update channel'
base['on']['push']['paths'] = ['.github/workflows/deliver-preview45.yml']
base['concurrency']['group'] = 'analyst-owner-preview45-delivery'
steps = base['jobs']['deliver']['steps']
old_run = steps[1]['run']
prefix = old_run[:old_run.index('remote =')]
remote = 'import subprocess\nresult=subprocess.run(' + repr(['/opt/analyst-ai/venv/bin/python', '-c', publisher]) + ',stdin=subprocess.DEVNULL,timeout=180)\nraise SystemExit(result.returncode)\n'
verification = '''output = with_ams(remote, timeout=240, capture=True).decode('utf-8')
assert len(output.encode()) <= 65536
def one(prefix):
    rows = [line.split('=', 1)[1] for line in output.splitlines() if line.startswith(prefix + '=')]
    assert len(rows) == 1
    return json.loads(rows[0])
publication = one('OWNER_PREVIEW45_DELIVERY')
observations = one('OWNER_PREVIEW45_CLIENT_OBSERVATIONS')
for key, value in EXPECTED_AUTH.items():
    assert type(publication[key]) is type(value) and publication[key] == value, key
assert publication['version_name'] == '0.13.7-preview' and publication['channel_version'] == 45
assert publication['previous_version'] == 44 and publication['previous_apk_sha256'] == OLD_SHA
assert observations['physical_phone_verified'] is False and observations['client_headers_are_not_device_attestation'] is True
origin = 'https://analyst-ai-2941515.twc1.net'
expected_path = '/client/apk/Analyst-AI-45-' + publication['apk_sha256'] + '.apk'
assert publication['url'] == origin + expected_path
opener = urllib.request.build_opener(p.NoRedirect(), urllib.request.HTTPSHandler(context=p.verified_ssl_context()))
def public_json(url, limit):
    with opener.open(urllib.request.Request(url, headers={'Cache-Control': 'no-cache'}), timeout=45) as response:
        assert response.status == 200 and response.headers.get_content_type() == 'application/json'
        raw = response.read(limit + 1)
        assert len(raw) <= limit
        return json.loads(raw)
def checked_policy():
    policy = public_json(origin + '/client/update-policy?package_name=ru.omnicio.app.debug', 16384)
    for key in ('version_code', 'version_name', 'apk_sha256', 'apk_bytes', 'certificate_sha256', 'published_at'):
        assert type(policy[key]) is type(publication[key]) and policy[key] == publication[key]
    assert policy['package_name'] == 'ru.omnicio.app.debug' and policy['min_sdk'] == 37
    assert policy['minimum_version_code'] == 45 and policy['version_is_not_attestation'] is True
    assert policy['apk_path'] == expected_path
    return policy
policy = checked_policy()
digest = hashlib.sha256()
size = 0
with opener.open(urllib.request.Request(publication['url'], headers={'Cache-Control': 'no-cache'}), timeout=120) as response:
    assert response.status == 200 and response.headers.get_content_type() == 'application/vnd.android.package-archive'
    assert response.headers.get('Content-Length') in (None, str(publication['apk_bytes']))
    for block in iter(lambda: response.read(1024**2), b''):
        size += len(block)
        assert size <= publication['apk_bytes']
        digest.update(block)
assert size == publication['apk_bytes'] and digest.hexdigest() == publication['apk_sha256']
assert checked_policy() == policy and public_json(origin + '/health', 1024) == {'status': 'ok'}
verification = {'schema': 1, 'kind': 'owner_preview45_public_delivery', 'publication': publication,
    'client_observations_at_publication': observations, 'https_policy_verified': True,
    'https_entire_apk_download_verified': True, 'https_apk_bytes': size, 'https_apk_sha256': digest.hexdigest(),
    'backend_health_http': 200, 'backend_health_body': {'status': 'ok'},
    'physical_phone_verified': False, 'complete_release_gate_passed': False}
out = pathlib.Path(os.environ['RUNNER_TEMP']) / 'owner-preview45-public-verification.json'
with out.open('x', encoding='utf-8') as target:
    json.dump(verification, target, ensure_ascii=False, sort_keys=True, indent=2)
    target.write('\\n')
print('OWNER_PREVIEW45_PUBLIC_VERIFIED=' + json.dumps(verification, ensure_ascii=True), flush=True)
'''
steps[1]['run'] = prefix + 'remote = ' + repr(remote) + '\nEXPECTED_AUTH = ' + repr(authorization) + '\nOLD_SHA = ' + repr(old_sha) + '\n' + verification + '\nPY\n'
steps[1]['name'] = 'Require exact native evidence, publish preview45 and verify complete HTTPS delivery'
steps[2]['with'] = {key: (value.replace('preview44', 'preview45') if isinstance(value, str) else value)
                   for key, value in steps[2]['with'].items()}
output = here / 'deliver-preview45.yml'
output.write_text(yaml.safe_dump(base, allow_unicode=True, sort_keys=False, width=160))
assert yaml.safe_load(output.read_text()) == base
print(json.dumps({'workflow': str(output), 'apk': apk, 'build_run': build_run,
                  'source': options.source_commit, 'native_run': options.native_run,
                  'publication_performed': False}, indent=2))
