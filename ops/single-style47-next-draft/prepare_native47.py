"""Bind native47 diagnostics to original successful Windows build evidence.

Administrative text generation only. Application and native test execution is
restricted to LAPTOP-NPSGA016 by the preserved Windows runtime controller.
"""
from pathlib import Path, PureWindowsPath
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import re

import yaml

HERE = Path(__file__).resolve().parent
CONTEXT = HERE.parent
TARGET = '.github/workflows/windows-n00-design47.yml'
PINS = {
    'prepare_native44.py': 'f3f1321d3f3e5d8c0f2244b932fe055b29953abc4e202af0bb982ab3d8e32dc2',
    'native44-bound/n00-runtime.py': 'b5479dcb488eed6e38a1c2dc40d21b43e6ce61aeeaed644037be169e4d0d0cb9',
    'native44-bound/workflow.yml': '9ee2325a8746d5123d0ae07792195639b50f1e738f9f10466fa1c59d04e391d8',
    'single-style47-runtime-deployment/prepare-deployment.py': 'dbafd2466f38cb876e0a09dc059c5ea1c97f00ccefc798772c4127e5460f2f0e',
    'design47/native47-focus-hook.py': '05b8008ea68b221b27d8bb61160c88db5bd4fdae606cc22e41f8a102c8fe6858',
}
APKS = ('app/build/outputs/apk/preview/app-preview.apk',
        'app/build/outputs/apk/debug/app-debug.apk',
        'ci-ui-driver/build/outputs/apk/debug/ci-ui-driver-debug.apk')
CERT = 'bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1'


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def pinned(name):
    path = CONTEXT / name
    need(path.resolve(strict=True) == path and path.is_file() and not path.is_symlink(), 'canonical_pinned_input_required')
    raw = path.read_bytes()
    need(0 < len(raw) <= 8 * 1024**2 and sha(raw) == PINS[name], 'pinned_input_changed: ' + name)
    return raw


def admin(name):
    raw = pinned(name)
    ast.parse(raw)
    spec = importlib.util.spec_from_file_location('native47_admin_' + Path(name).stem, CONTEXT / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(request):
    need(set(request) == {'schema', 'build_request', 'baseline_publication'} and request['schema'] == 1,
         'unexpected_native47_request')
    verifier = admin('single-style47-runtime-deployment/prepare-deployment.py')
    helper = verifier.helper_module()
    build_request, _ = helper.evidence(request, 'build_request')
    expected, inventory = verifier.validate(helper, build_request)
    report, report_raw = helper.evidence(build_request, 'build_report')
    exported, export_raw = helper.evidence(build_request, 'build_export_receipt')
    publication, publication_raw = helper.evidence(request, 'baseline_publication')
    published = publication['publication']
    baseline = {'version_code': 45, 'version_name': '0.13.7-preview', 'bytes': 29820407,
                'sha256': '488f95a0c1527ebf5a172c7af675769cb8ed81c116d9ec24175fc89adab1da0d',
                'retained_build_run_id': 40342969750,
                'source_sha256': 'de9339350d25e0f3731f8ccc3702f8be5d2a2110b2433b1c5d9ea74035e51d89'}
    need(publication['https_policy_verified'] is True and publication['https_entire_apk_download_verified'] is True
         and publication['backend_health_http'] == 200
         and publication['https_apk_bytes'] == published['apk_bytes'] == baseline['bytes']
         and publication['https_apk_sha256'] == published['apk_sha256'] == baseline['sha256']
         and published['version_code'] == published['channel_version'] == 45
         and published['version_name'] == baseline['version_name'] and published['package_name'] == 'ru.omnicio.app.debug'
         and published['certificate_sha256'] == CERT
         and published['source_sha256'] == baseline['source_sha256']
         and published['windows_run_id'] == baseline['retained_build_run_id'], 'actual_published45_baseline_required')
    baseline.update(publication_receipt_sha256=sha(publication_raw), published_at=published['published_at'])
    files = {}
    for name in APKS:
        value = report['apks'][name]
        need(set(value) == {'bytes', 'sha256'} and type(value['bytes']) is int
             and 0 < value['bytes'] <= 128 * 1024**2 and re.fullmatch('[a-f0-9]{64}', value['sha256']),
             'invalid_original47_apk_identity')
        files[name] = [value['bytes'], value['sha256']]
    need(files[APKS[0]][1] == report['build']['apk_sha256'] != baseline['sha256'], 'candidate47_apk_must_differ')
    hook = pinned('design47/native47-focus-hook.py')
    provenance = {
        'build_report_sha256': sha(report_raw), 'build_run_id': expected['github']['run_id'],
        'build_run_attempt': expected['github']['run_attempt'], 'build_workflow_sha': expected['github']['workflow_sha'],
        'build_status': report['status'], 'host': 'LAPTOP-NPSGA016', 'root': report['root'], 'state': report['state'],
        'build_base_commit': report['base_commit'], 'source_backup_commit': expected['source_backup_commit'],
        'source_sha256': expected['source_sha256'], 'complete_build_source_sha256': expected['complete_source_sha256'],
        'build_export_receipt_sha256': sha(export_raw), 'build_archive': expected['archive'],
        'preview_version_code': 47, 'preview_version_name': '0.14.0-preview', 'input_apks': files,
        'candidate_source_files': inventory, 'baseline': baseline, 'native_hook_sha256': sha(hook),
        'page_size_profiles': [16384, 4096], 'required_fonts': [1.0, 2.0], 'required_icons_per_font': 21,
        'required_destination_pages': ['strategy', 'markets', 'notifications', 'assistant', 'appearance', 'library'],
        'original_portfolio_executed': False, 'full_ui_stage_count': 15, 'diagnostic_only': True,
        'release_gate_pass': False, 'full_ui_suite_executed': False, 'publication_authorized': False,
        'phone_verified': False,
    }
    # Native helpers and fixture callbacks must belong to this exact build.
    for name in ('.github/scripts/automation_ui_probe.py', '.github/scripts/navigation_detail_probe.py',
                 '.github/scripts/profile_ui_probe.py', '.github/scripts/profile_scroll.py',
                 'app/src/main/java/ru/omnicio/app/ui/DockPredictiveBack.kt'):
        need(name in inventory, 'required47_native_source_missing: ' + name)
    return files, inventory, provenance, report_raw, export_raw, hook


SUMMARY = r'''const fs=require('node:fs'),p=require('node:path'),crypto=require('node:crypto');
const base=p.join(process.env.SOURCE_ROOT,'app/build/outputs/apk/preview');
const pages={};
let complete=true;
for (const [page,folder] of [[16384,'ui-screens-api37-16384'],[4096,'ui-screens']]) {
  const file=p.join(base,folder,'design47-focused-observations.json');
  if (!fs.existsSync(file)) { complete=false; pages[page]={missing:true}; continue; }
  const bytes=fs.readFileSync(file), value=JSON.parse(bytes.toString('utf8'));
  const valid=value.schema_version===1 && value.diagnostic_only===true && value.release_gate_pass===false
    && value.full15_executed===false && value.status==='passed' && value.fixture_apk_sha256===identity.debug_apk_sha256
    && value.actual_device_observations===true && value.cases.length===2
    && JSON.stringify(value.cases.map(c=>c.font_scale).sort())==='[1,2]'
    && value.appearance_restart_cases.length===2
    && JSON.stringify(value.appearance_restart_cases.map(c=>c.font_scale).sort())==='[1,2]'
    && value.appearance_restart_cases.every(c=>c.force_stop_and_relaunch===true
      && c.previous_process_id!==c.restarted_process_id && c.save_button_pressed===false
      && c.server_mutations===0 && c.after_restart.writes===0 && c.after_restore.writes===0
      && c.after_restart.preferences===c.persisted
      && c.before.preferences===c.after_restore.preferences && c.captures.length===2)
    && value.autosave_cases.length===2
    && JSON.stringify(value.autosave_cases.map(c=>c.font_scale).sort())==='[1,2]'
    && value.autosave_cases.every(c=>c.invalid_draft_retained===true && c.invalid_server_writes===0
      && c.invalid.writes===0 && c.invalid_after_navigation.writes===0
      && c.server_mutations===2 && c.saved.writes===2 && c.after.writes===2
      && c.valid_horizon_months===48 && c.confirmed_version===4
      && c.save_or_confirm_button_pressed===false && c.navigation_preserved_saved_value===true
      && c.process_id===c.process_id_after && c.minimum_touch_dp===48)
    && value.cases.every(c=>c.icons.length===21 && new Set(c.icons.map(i=>i.id)).size===21
      && JSON.stringify(c.destinations.map(d=>d.page))===JSON.stringify(identity.destinations)
      && c.automatic_appearance.length===2 && c.server_mutations===0 && c.minimum_touch_dp===48
      && c.predictive_back.underlying_page_unchanged===true && c.outside.underlying_page_unchanged===true
      && c.before.preferences===c.after.preferences && c.process_id===c.process_id_after);
  if(!valid) complete=false;
  pages[page]={complete:valid,bytes:bytes.length,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),observations:value};
}
const report={schema:1,...identity,design47_complete:complete,pages,diagnostic_only:true,
  release_gate_pass:false,full15_executed:false,physical_phone_verified:false};
const state=p.join(process.env.RUNNER_TEMP,'n00-native47-focused-'+process.env.GITHUB_RUN_ID+'-'+process.env.GITHUB_RUN_ATTEMPT);
fs.writeFileSync(p.join(state,'native47-design-summary.json'),JSON.stringify(report,null,2)+'\n');
core.setOutput('design47_complete',String(complete));
core.info('N00_DESIGN47_COMPLETE='+String(complete));
core.info('N00_FULL15_ACCEPTED=false');
await github.rest.checks.create({...context.repo,name:'N00 candidate47 dock observations (diagnostic only)',
  head_sha:context.sha,status:'completed',conclusion:'neutral',output:{
    title:complete?'Focused dock observations completed; full matrix remains pending':'Focused dock observations incomplete',
    summary:JSON.stringify({design47_complete:complete,source_sha256:identity.source_sha256,
      native_hook_sha256:identity.native_hook_sha256,full15_executed:false})}});
'''


def render(files, inventory, provenance, report_raw, export_raw, hook):
    helper = admin('prepare_native44.py')
    original = pinned('native44-bound/n00-runtime.py').decode()
    runtime = original
    for name, value in (('BASE_COMMIT', provenance['source_backup_commit']), ('SOURCE_HASH', provenance['source_sha256']),
                        ('SOURCE_EVIDENCE', inventory), ('BUILD_PROVENANCE', provenance), ('FILES', files),
                        ('PATCH_HASH', sha(hook))):
        runtime = helper.assignment(runtime, name, value)
    runtime = helper.replace_once(runtime, "PREVIOUS_HASH='4e9bf0a2fd54d8ab4b9d49ef9ddf96bc14a274ac4c145585fcfdb88d6ae774b6'",
                                  'PREVIOUS_HASH=' + repr(provenance['baseline']['sha256']))
    line = next(line for line in runtime.splitlines() if line.startswith('BASELINE = '))
    baseline_root = PureWindowsPath('C:/actions-runner/_work/omni-cio-gateway/omni-cio-gateway/windows-development-40342969750-1')
    runtime = helper.replace_once(runtime, line, 'BASELINE = pathlib.Path(' + repr(str(baseline_root / APKS[0])) + ')')
    need(runtime.count('st_size==29771254') == 2, 'original_baseline_size_guards_changed')
    runtime = runtime.replace('st_size==29771254', 'st_size==29820407')
    replacements = (
        ('n00-native44-focused-', 'n00-native47-focused-'),
        ('native44-build-provenance.json', 'native47-build-provenance.json'),
        ('native44-evidence-envelope.json', 'native47-evidence-envelope.json'),
        ('n00_candidate44_portfolio_focused', 'n00_candidate47_design_focused'),
        ('previous43.apk', 'previous45.apk'), ('published_baseline43_changed', 'published_baseline45_changed'),
        ('n00-portfolio-focused-hook.py', 'n00-design47-focused-hook.py'),
    )
    for old, new in replacements:
        need(old in runtime, 'native_template_anchor_missing: ' + old)
        runtime = runtime.replace(old, new)
    runtime = helper.replace_once(runtime, 'def unchanged():\n',
        "def unchanged():\n    hook=pathlib.Path(os.environ['RUNNER_TEMP'])/'n00-design47-focused-hook.py'\n"
        "    need(regular(hook).st_size==" + str(len(hook)) + " and sha(hook)==PATCH_HASH,'native47_hook_changed')\n")
    # Only metadata, baseline identity and the independently bound hook change.
    before = {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(original).body
              if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    after = {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(runtime).body
             if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    need(set(before) == set(after), 'native_controller_function_set_changed')
    for name in before.keys() - {'unchanged', 'prepare', 'profile', 'export'}:
        need(before[name] == after[name], 'native_ownership_or_environment_helper_changed: ' + name)
    ast.parse(hook)
    template = yaml.safe_load(pinned('native44-bound/workflow.yml'))
    workflow = copy.deepcopy(template)
    workflow['name'] = 'Observe actual candidate47 dock and automatic appearance at both API37 page sizes'
    workflow['on']['push']['paths'] = [TARGET]
    workflow['concurrency']['group'] = 'analyst-n00-candidate47-design-focused'
    need(workflow['concurrency']['cancel-in-progress'] is False, 'native_cancellation_changed')
    job = workflow['jobs']['develop']
    job['name'] = 'Observe exact47 preview installation and production icon dock on Windows'
    job['timeout-minutes'] = 140
    job['outputs'].pop('original14_complete')
    job['outputs']['design47_complete'] = '${{ steps.focused_report.outputs.design47_complete }}'
    steps, staged = [], False
    for step in job['steps']:
        if step.get('name', '').startswith('Stage verified focused transport '):
            if not staged:
                additions = [helper.stage('n00-runtime.py', runtime.encode()),
                    helper.stage('n00-design47-focused-hook.py', hook),
                    helper.stage('n00-successful-build-report.json', report_raw),
                    helper.stage('n00-build-export-receipt.json', export_raw)]
                additions[-1]['id'] = 'setup'
                steps.extend(additions); staged = True
            continue
        if step.get('uses', '').startswith('actions/checkout@'):
            need(step['with']['ref'] == '1cc05586b6874bfdd0cdb80131d178de9f95870c'
                 and step['with']['persist-credentials'] is False, 'native_checkout_template_changed')
            step['with']['ref'] = provenance['source_backup_commit']
        if step.get('id') == 'prepare':
            step['name'] = 'Bind exact successful47 build, full source inventory and published45 baseline'
        if step.get('id') == 'runtime16':
            step['name'] = 'Actual icon dock, outside/Back dismissal and automatic appearance on API37 16KB'
        if step.get('id') == 'focused_report':
            identity = {key: provenance[key] for key in ('source_sha256', 'source_backup_commit', 'build_run_id',
                        'build_run_attempt', 'build_report_sha256', 'native_hook_sha256')}
            identity.update(debug_apk_sha256=files[APKS[1]][1], destinations=provenance['required_destination_pages'])
            step['with']['script'] = 'const identity=' + json.dumps(identity, separators=(',', ':')) + ';\n' + SUMMARY
            step['name'] = 'Report bounded native47 observations separately from full15 acceptance'
        if step.get('uses', '').startswith('actions/upload-artifact@'):
            step['name'] = 'Retain original47 install receipts, live native observations and synthetic screenshots'
            step['with']['name'] = 'n00-candidate47-design-native-both-pages'
            step['with']['path'] = step['with']['path'].replace('n00-native44-focused-', 'n00-native47-focused-')
            step['with']['path'] += '\n${{ env.SOURCE_ROOT }}/app/build/outputs/apk/preview/install-api37-4096/*.json' \
                                   '\n${{ env.SOURCE_ROOT }}/app/build/outputs/apk/preview/install-api37-4096/*.log'
        need(not step.get('continue-on-error'), 'native_failures_must_remain_visible')
        steps.append(step)
        if step.get('id') == 'runtime16':
            four = copy.deepcopy(step)
            four.update(id='runtime4', name='The same real dock observations on API37 4KB',
                        **{'if': "always() && steps.prepare.outcome == 'success'"})
            four['run'] = four['run'].replace('16384', '4096')
            steps.append(four)
    need(staged, 'native_transport_not_staged')
    job['steps'] = steps
    for name in ('preflight', 'collect', 'cleanup'):
        need(workflow['jobs'][name] == template['jobs'][name], 'private_transport_changed: ' + name)
    workflow['jobs']['result']['name'] = 'Focused design47 diagnostics do not claim full15 runtime acceptance'
    result_step = workflow['jobs']['result']['steps'][0]
    result_step['run'] = result_step['run'].replace('Focused portfolio evidence collected', 'Focused design47 evidence collected')
    output = {'n00-runtime.py': runtime.encode(), 'n00-design47-focused-hook.py': hook,
              'n00-successful-build-report.json': report_raw, 'n00-build-export-receipt.json': export_raw,
              'build-provenance.json': encoded(provenance),
              'workflow.yml': yaml.safe_dump(workflow, allow_unicode=True, sort_keys=False, width=120).encode()}
    need(yaml.safe_load(output['workflow.yml']) == workflow, 'workflow_roundtrip_changed')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    request_path = args.request.absolute()
    need(CONTEXT in request_path.parents and request_path.resolve(strict=True) == request_path, 'canonical_request_required')
    raw = request_path.read_bytes()
    need(sha(raw) == args.request_sha256 and len(raw) < 16384, 'native_request_changed')
    values = validate(json.loads(raw))
    outputs = render(*values)
    destination = args.output.absolute()
    need(destination.parent == CONTEXT and not destination.exists(), 'new_context_output_required')
    receipt = {'schema': 1, 'state': 'prepared_only_not_executed', 'target_workflow': TARGET,
        'request_sha256': sha(raw), 'build_run_id': values[2]['build_run_id'],
        'source_backup_commit': values[2]['source_backup_commit'], 'source_sha256': values[2]['source_sha256'],
        'native_hook_sha256': sha(values[5]), 'application_or_test_execution': False,
        'full15_accepted': False, 'apk_publication_performed': False,
        'files': {name: {'bytes': len(data), 'sha256': sha(data)} for name, data in outputs.items()}}
    outputs['preparation.json'] = encoded(receipt)
    destination.mkdir()
    for name, data in outputs.items():
        with (destination / name).open('xb') as stream:
            stream.write(data)
    print(json.dumps({key: value for key, value in receipt.items() if key != 'files'}))


if __name__ == '__main__':
    main()
