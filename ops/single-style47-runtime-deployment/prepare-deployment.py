"""Prepare, but never execute, the exact tested46 three-file runtime deployment.

Requires real completed Windows47 reports, original inventory and an actual
source backup commit. The generated hosted job independently verifies all five
build jobs and the backup's entire code tree before opening the pinned transport.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re

import yaml

HERE = Path(__file__).resolve().parent
CONTEXT = HERE.parent
WORKSPACE = CONTEXT.parent
TARGET = '.github/workflows/single-style47-web-runtime-deployment.yml'
ASSETS_SHA = 'a320b29b48f408945d9f446070a9ef126262e31c806a60fa4123d7367ae3fd50'
ROUTING_SHA = 'ba03f61215f07602830d295e8a5257444c58dba6735d737ba2771ff44254f1be'
PRIOR_SHA = '599df7ca37ab4cc9a98effdf4a2688911e6d0225edf762d0d72298d0e954f477'
ROUTE_HELPERS_SHA = '79c73c55a07e5a96f92c84ad89982dd84a3655598b64a90d774b28781bcca177'
TRANSPORT_SHA = '11eb69a59124adb8042b9b811cd652bc34ae282c7907f3e6e31493ade9bbe91d'
TRANSPORT_PREFIX_SHA = '5569d1c96c52b11766e5f9a2610a442827693491360cd5c051f1b86dc0531800'
WORKFLOW_SHA = '3b3788939022a2227a3b8d2c41079eb0a7d5c5f8428eeb875c00cc2e90a4bc85'
HELPER_SHA = '64db4d35e4fa983ac0d90f0398a9edbfed6263851fe03f1460c9671828ff8ab4'
TEMPLATE_PINS = {'deploy-runtime.py': 'cf26d63c472722296f2b6fb955776b59bb2028e07f0473ec54afa04b4f925e2e', 'public-checks.py': '52d1af965802c2ed4130cbc04761fbc283a82b3e97219b0ec4d72342a87ab2f0', 'receive-deployment.py': 'bd46273fce3c4273d5b76fa50aecb1b0e45d606259aa807082987ac75ea3e06f'}
WEB_NAMES = ('app.py', 'telegram_browser_app.py', 'owner_app.py')
REQUIRED_CHECKS = {'host-tests', 'tools-tests', 'node-tests', 'backend-tests', 'gradle', 'apk-verification'}


def need(value, code):
    if not value:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def checked(path, expected, maximum=8 * 1024**2):
    need(CONTEXT in path.parents and path.resolve(strict=True) == path and path.is_file(), 'canonical_context_input_required')
    before = path.stat()
    need(before.st_nlink == 1 and 0 < before.st_size <= maximum, 'bounded_input_required')
    raw = path.read_bytes()
    after = path.stat()
    need((before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns)
         and sha(raw) == expected, 'input_identity_changed')
    return raw


def helper_module():
    path = CONTEXT / 'prep/delivery44/prepare_delivery44.py'
    raw = checked(path, HELPER_SHA)
    ast.parse(raw)
    spec = importlib.util.spec_from_file_location('administrative_evidence46', path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


def inventory_validate(helper, value, code, complete):
    need(set(value) == {'files', 'source_sha256', 'complete_source_sha256'} and
         type(value['files']) is dict and 1 <= len(value['files']) <= 20000, 'invalid_actual_inventory')
    a, b, seen = hashlib.sha256(), hashlib.sha256(), set()
    for name, row in sorted(value['files'].items(), key=lambda item: item[0].encode('utf-8')):
        path = PurePosixPath(name)
        need(path.as_posix() == name and not path.is_absolute() and '..' not in path.parts and
             not any(character in name for character in ('\\', ':', '\0', '\n', '\r')) and
             name.casefold() not in seen, 'unsafe_actual_inventory_path')
        seen.add(name.casefold())
        need(set(row) == {'bytes', 'sha256'} and type(row['bytes']) is int and 0 <= row['bytes'] <= 128 * 1024**2,
             'invalid_actual_inventory_file')
        helper.digest(row['sha256'])
        record = name.encode('utf-8') + b'\0' + row['sha256'].encode('ascii') + b'\0'
        b.update(record)
        if name not in ('AGENTS.md', 'README.md') and not name.startswith('docs/'):
            a.update(record)
    need(a.hexdigest() == code == value['source_sha256'] and b.hexdigest() == complete == value['complete_source_sha256'],
         'actual_inventory_hash_changed')


def callback_style(raw):
    module = ast.parse(raw)
    function = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == 'mobile_login_result')
    pages = [node.value for node in ast.walk(function) if isinstance(node, ast.Assign) and
             any(isinstance(target, ast.Name) and target.id == 'page' for target in node.targets)]
    need(len(pages) == 1 and isinstance(pages[0], ast.JoinedStr), 'callback_page_structure_changed')
    fragments = [node.value for node in pages[0].values if isinstance(node, ast.Constant) and type(node.value) is str]
    styles = [fragment.split('<style>', 1)[1].split('</style>', 1)[0]
              for fragment in fragments if fragment.count('<style>') == 1 and fragment.count('</style>') == 1]
    need(len(styles) == 1 and '--bg: #050E1C;' in styles[0] and 'color-scheme: dark;' in styles[0] and 'prefers-color-scheme' not in styles[0],
         'exact_reviewed_single_style_css_required')
    callback = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == 'telegram_callback')
    early = callback.body[0]
    need(isinstance(early, ast.If) and ast.unparse(early.test) == 'error is not None' and len(early.body) == 1 and
         isinstance(early.body[0], ast.Return) and ast.unparse(early.body[0].value) == "mobile_login_result(error='telegram_denied')",
         'callback_error_must_return_before_any_database_or_handoff_state_change')
    return sha(styles[0].encode('utf-8'))


def validate(helper, request):
    required = {'schema', 'candidate_version_code', 'candidate_version_name', 'source_backup_commit', 'source_sha256',
                'build_report', 'build_controller', 'build_export_receipt', 'source_inventory', 'reviewed_manifest', 'prepared_build'}
    need(type(request) is dict and set(request) == required and request['schema'] == 1 and
         type(request['candidate_version_code']) is int and request['candidate_version_code'] == 47 and
         request['candidate_version_name'] == '0.14.0-preview', 'only_exact_candidate47_request_is_supported')
    helper.digest(request['source_backup_commit'], 40)
    source = helper.digest(request['source_sha256'])
    values, raws = {}, {}
    for name in required - {'schema', 'candidate_version_code', 'candidate_version_name', 'source_backup_commit', 'source_sha256'}:
        values[name], raws[name] = helper.evidence(request, name)
    build, controller, exported = values['build_report'], values['build_controller'], values['build_export_receipt']
    inventory, reviewed, prepared = values['source_inventory'], values['reviewed_manifest'], values['prepared_build']
    run = helper.positive(build['github']['run_id'])
    attempt = helper.positive(build['github']['run_attempt'], 99999)
    helper.digest(build['github']['workflow_sha'], 40)
    helper.build_root(build['root'], run, attempt)
    base = helper.digest(build['base_commit'], 40)
    base_code = helper.digest(build['base_source_sha256'])
    need(request['source_backup_commit'] != base and build['schema'] == 1 and
         build['kind'] == 'windows_development_check_build' and build['origin'] == 'Windows laptop' and
         build['host'] == 'LAPTOP-NPSGA016', 'completed_windows47_source_backup_required')
    need(build['status'] == 'passed_check_and_build_only' and
         all(build[key]['status'] == 'passed' and build[key]['source_sha256'] == source for key in ('check', 'build')) and
         build['source_sha256'] == build['source_sha256_after'] == source, 'windows47_full_check_build_not_passed')
    complete = helper.digest(build['complete_source_sha256'])
    need(build['complete_source_sha256_after'] == complete and build['certificate_sha256'] == helper.CERT and
         all(build[key] is False for key in ('publication_authorized', 'phone_verified', 'timeweb_execution')) and
         build['runtime']['status'] == 'not_run', 'windows47_scope_or_signing_changed')
    labels = [row['label'] for row in build['steps']]
    need(len(labels) == len(set(labels)) and REQUIRED_CHECKS <= set(labels) and
         all(type(row['exit_code']) is int and row['exit_code'] == 0 for row in build['steps']),
         'all_windows47_phases_must_pass')
    need(controller['worker_started'] is True and type(controller['worker_exit_code']) is int and
         controller['worker_exit_code'] == 0 and controller['owned_processes_after'] == 0 and
         controller.get('finished_at') and controller.get('lease_acquired_at') and
         not controller.get('error') and not controller.get('cleanup_error'), 'windows47_cleanup_incomplete')
    need(PureWindowsPath(controller['lease']) == PureWindowsPath(
        'C:/Windows/ServiceProfiles/NetworkService/AppData/Local/Temp/analyst-ai-emulator-lease/android.lock'),
        'canonical_windows_lease_changed')
    need(exported['status'] == 'passed_check_and_build_only' and exported['source_sha256'] == source and
         exported['complete_source_sha256'] == complete and exported['runtime_pass'] is False and
         exported['publication_authorized'] is False, 'wrong_successful_windows47_export')
    helper.positive(exported['bytes'], 256 * 1024**2)
    helper.positive(exported['files'], 20000)
    helper.digest(exported['sha256'])
    need(prepared['base_commit'] == base and prepared['base_source_sha256'] == base_code and
         prepared['bootstrap_sha256'] == build['bootstrap_sha256'] and
         prepared['patch_manifest_sha256'] == build['patch_manifest_sha256'] and
         prepared['reviewed_files_sha256'] == sha(raws['reviewed_manifest']), 'windows47_reviewed_transport_mismatch')
    need(reviewed['schema'] == 1 and reviewed['version_before'] == {'code': 45, 'name': '0.13.7'} and
         reviewed['version_after'] == {'code': 47, 'name': '0.14.0'}, 'reviewed47_version_identity_changed')
    rows = {row['path']: row for row in reviewed['files']}
    patches = {row['path']: row for row in build['patch_files']}
    need(len(rows) == len(reviewed['files']) and len(patches) == len(build['patch_files']) and
         set(rows) == set(patches), 'windows47_patch_scope_changed')
    inventory_validate(helper, inventory, source, complete)
    for name, row in rows.items():
        raw = row['content'].encode('utf-8')
        need(len(raw) == row['new_bytes'] and sha(raw) == row['new_sha256'] and
             patches[name]['old_sha256'] == row['old_sha256'] and patches[name]['new_sha256'] == row['new_sha256'] and
             inventory['files'][name] == {'bytes': len(raw), 'sha256': sha(raw)}, 'windows47_reviewed_file_mismatch')
    gradle = rows['app/build.gradle.kts']['content']
    need(re.search(r'\bversionCode\s*=\s*47\b', gradle) and
         re.search(r'\bversionName\s*=\s*"0\.14\.0"', gradle), 'actual47_version_source_missing')
    asset_rows = rows
    routing = helper.decoded(checked(CONTEXT / 'theme46-runtime-routing/actual-routing.json', ROUTING_SHA))
    prior = helper.decoded(checked(CONTEXT / 'theme46-runtime-observer/actual-runtime-comparison.json', PRIOR_SHA))
    need(routing['runtime_server_id'] == 9417611 and routing['public_host'] == 'analyst-ai-2941515.twc1.net' and
         routing['services']['analyst-ai-owner.service']['invocation']['owner_factory_binding_verified'] is True and
         routing['services']['analyst-ai-updates.service']['invocation']['public_update_factory_binding_verified'] is True and
         routing['routing']['counts']['file_server'] == routing['routing']['counts']['inline_html'] == 0,
         'observed_owner_factory_and_routing_required')
    web_sources = {}
    for name in (*WEB_NAMES, 'tests/test_owned_web_theme.py'):
        key = 'backend/' + name
        row, current = asset_rows[key], rows[key]
        raw = row['content'].encode('utf-8')
        need(current['new_sha256'] == row['new_sha256'] and current['new_bytes'] == len(raw) and
             current['content'].encode('utf-8') == raw, 'actual47_web_slice_differs_from_reviewed_bytes')
        if name in WEB_NAMES:
            old = routing['sources']['/opt/analyst-ai/backend/' + name]
            need(old['status'] == 'observed' and old['matches_reference44'] is True and
                 old['sha256'] == row['old_sha256'] == current['old_sha256'] and old['bytes'] == row['old_bytes'] and
                 old['bytes'] != len(raw), 'runtime_old_web_identity_or_bytecode_invalidation_changed')
            web_sources[name] = {'old': {key: old[key] for key in ('bytes', 'sha256')},
                                 'new': {'bytes': len(raw), 'sha256': sha(raw)}}
    tests = ast.parse(rows['backend/tests/test_owned_web_theme.py']['content'])
    names = [node.name for node in ast.walk(tests) if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
    need(len(names) == len(set(names)) == 6, 'exact_six_html_security_tests_required')
    expected = {'schema': 1, 'source_backup_commit': request['source_backup_commit'], 'source_sha256': source,
                'reviewed_manifest_sha256': sha(raws['reviewed_manifest']),
                'complete_source_sha256': complete, 'base_commit': base, 'base_source_sha256': base_code,
                'github': build['github'], 'archive': {key: exported[key] for key in ('bytes', 'sha256')},
                'archive_files': exported['files'],
                'archive_path': f'/var/lib/analyst-ai-build/incoming/windows-development-{run}-{attempt}/windows-development-evidence.zip',
                'web_sources': web_sources, 'web_test_names': names,
                'web_test_source': inventory['files']['backend/tests/test_owned_web_theme.py'],
                'callback_style_sha256': callback_style(rows['backend/app.py']['content']),
                'services': routing['services'],
                'units': {'/etc/systemd/system/' + name: {key: row['unit_file_identity'][key] for key in ('bytes', 'sha256')}
                          for name, row in routing['services'].items()},
                'active_caddy': {key: routing['active_caddy_configuration'][key] for key in ('bytes', 'sha256')},
                'caddy_file': {key: prior['configuration_file_identities']['/etc/caddy/Caddyfile'][key] for key in ('bytes', 'sha256')},
                'untouched_sources': {name: {key: row[key] for key in ('bytes', 'sha256')}
                                      for name, row in routing['sources'].items()
                                      if name not in {'/opt/analyst-ai/backend/' + file for file in WEB_NAMES}}}
    for name in ('build_report', 'build_controller', 'source_inventory'):
        expected[name] = {'bytes': len(raws[name]), 'sha256': sha(raws[name])}
    code_files = {name: row for name, row in inventory['files'].items()
                  if name not in ('AGENTS.md', 'README.md') and not name.startswith('docs/')}
    return expected, code_files


def functions(text, names):
    nodes = [node for node in ast.parse(text).body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    need(len(nodes) == len(names), 'pinned_administrative_helper_set_changed')
    lines = text.splitlines(keepends=True)
    return '\n\n'.join(''.join(lines[node.lineno - 1:node.end_lineno]) for node in nodes)


def render(expected, code_files, request_sha):
    need(set(TEMPLATE_PINS) == {'deploy-runtime.py', 'public-checks.py', 'receive-deployment.py'}, 'template_freeze_required')
    templates = {name: checked(HERE / name, digest).decode('utf-8') for name, digest in TEMPLATE_PINS.items()}
    common = checked(CONTEXT / 'theme46-runtime-routing/prepared/observe-routes.py', ROUTE_HELPERS_SHA).decode('utf-8')
    helpers = functions(common, {'ObservationError', 'need', 'digest', 'identity', 'stable', 'trusted_read', 'observed_file',
                               'unique', 'active_caddy', 'bounded_systemctl', 'invocation', 'service_observation'})
    remote = templates['deploy-runtime.py']
    for marker in ('EXPECTED = {}', '# COMMON_HELPERS', '# PUBLIC_CHECKS'):
        need(remote.count(marker) == 1, 'remote_template_marker_changed')
    remote = remote.replace('EXPECTED = {}', 'EXPECTED = ' + repr(expected), 1).replace('# COMMON_HELPERS', helpers, 1)
    remote = remote.replace('# PUBLIC_CHECKS', templates['public-checks.py'], 1)
    transport = checked(CONTEXT / 'candidate44-recovery/hosted-recovery.py', TRANSPORT_SHA).decode('utf-8')
    node = next(node for node in ast.parse(transport).body if isinstance(node, ast.FunctionDef) and node.name == 'with_ams')
    prefix = ''.join(transport.splitlines(keepends=True)[:node.end_lineno])
    need(sha(prefix.encode('utf-8')) == TRANSPORT_PREFIX_SHA, 'pinned9417611_transport_changed')
    hosted = prefix + '\n\nEXPECTED = ' + repr(expected) + '\nSOURCE_FILES = ' + repr(code_files) + \
        '\nREMOTE_SHA256 = ' + repr(sha(remote.encode('utf-8'))) + '\nremote = ' + repr(remote) + '\n' + \
        templates['public-checks.py'] + '\n' + templates['receive-deployment.py']
    ast.parse(remote)
    ast.parse(hosted)
    old = yaml.safe_load(checked(CONTEXT / 'candidate44-recovery/workflow.yml', WORKFLOW_SHA))['jobs']['recover']['steps']
    checkout = copy.deepcopy(old[0])
    need(checkout['with']['ref'] == 'cd1866ee944ccea2259669f4293379241fd4ee02' and
         checkout['with']['persist-credentials'] is False and checkout['with']['path'] == '.transport-admin',
         'pinned_administrative_checkout_changed')
    backup = copy.deepcopy(checkout)
    backup['name'] = 'Read exact source47 backup and bind the complete built code inventory'
    backup['with'].update(ref=expected['source_backup_commit'], path='source-backup47')
    env = copy.deepcopy(old[1]['env'])
    env['GH_READ_TOKEN'] = '${{ github.token }}'
    deploy = {'name': 'Deploy only three Windows-tested HTML theme sources and verify bounded public routes',
              'shell': 'bash', 'env': env, 'run': "python - <<'PY'\n" + hosted + '\nPY\n'}
    upload = {'name': 'Retain bounded deployment and verification receipts', 'if': 'always()', 'uses': old[2]['uses'],
              'with': {'name': 'single_style47-web-runtime-deployment', 'retention-days': 3, 'if-no-files-found': 'warn',
                       'path': '${{ runner.temp }}/single_style47-web-deployment-${{ github.run_id }}-${{ github.run_attempt }}/*.json'}}
    workflow = {'name': 'Apply exact tested47 single style to the three active owner HTML surfaces',
                'on': {'push': {'branches': ['codex/timeweb-owner-prepare-2026-10-23'], 'paths': [TARGET]}},
                'permissions': {'contents': 'read', 'actions': 'read'},
                'concurrency': {'group': 'owner-preview-release-publication', 'cancel-in-progress': False},
                'jobs': {'deploy': {'runs-on': 'ubuntu-24.04', 'timeout-minutes': 20,
                                    'steps': [checkout, backup, deploy, upload]}}}
    raw_workflow = yaml.safe_dump(workflow, allow_unicode=True, sort_keys=False, width=120).encode('utf-8')
    need(yaml.safe_load(raw_workflow) == workflow, 'workflow_yaml_roundtrip_changed')
    output = {'deploy-runtime.py': remote.encode('utf-8'), 'hosted-deployment.py': hosted.encode('utf-8'),
              'workflow.yml': raw_workflow, 'expected-identities.json': encoded(expected)}
    output['preparation.json'] = encoded({'schema': 1, 'state': 'prepared_only_not_dispatched', 'request_sha256': request_sha,
        'target_workflow': TARGET, 'source_backup_commit': expected['source_backup_commit'],
        'source_sha256': expected['source_sha256'], 'runtime_routing_observation_sha256': ROUTING_SHA,
        'reviewed_manifest_sha256': expected['reviewed_manifest_sha256'], 'pinned_transport_prefix_sha256': TRANSPORT_PREFIX_SHA,
        'changed_runtime_files': ['/opt/analyst-ai/backend/' + name for name in WEB_NAMES],
        'application_or_test_execution_performed': False, 'server_mutation_performed': False,
        'apk_published_or_installed': False, 'help_deployed': False,
        'files': {name: {'bytes': len(raw), 'sha256': sha(raw)} for name, raw in output.items()}})
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    helper = helper_module()
    request_raw = checked(helper.path_under_context(args.request), args.request_sha256)
    expected, code_files = validate(helper, helper.decoded(request_raw))
    output = render(expected, code_files, sha(request_raw))
    destination = helper.path_under_context(args.output)
    need(destination.is_relative_to(HERE) and not destination.exists() and
         destination.parent.resolve(strict=True) == destination.parent, 'new_canonical_deployment_output_required')
    destination.mkdir()
    for name, raw in output.items():
        with (destination / name).open('xb') as stream:
            stream.write(raw)
    print(json.dumps({'prepared_only': str(destination), 'workflow_sha256': sha(output['workflow.yml']),
                      'application_or_test_execution_performed': False, 'server_mutation_performed': False}))


if __name__ == '__main__':
    main()
