import datetime, hashlib, json, os, pathlib, re, sys
import xml.etree.ElementTree as ET
assert sys.platform == 'win32' and os.environ.get('COMPUTERNAME') == 'LAPTOP-NPSGA016'
run = 40453334023
result = {'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'host': os.environ['COMPUTERNAME'], 'run_id': run, 'build': [], 'jvm': []}
for suffix in ('', '-2', '-3', '-4'):
    runner = pathlib.Path('C:/actions-runner' + suffix + '/_work')
    state = runner / ('_temp/analyst-development-' + str(run) + '-1')
    if state.is_dir():
        item = {'state': str(state), 'files': {}, 'log_tail': {}}
        for name in ('windows-development.json', 'controller.json', 'export-receipt.json'):
            path = state / name
            if not path.is_file() or path.is_symlink():
                continue
            raw = path.read_bytes()
            assert len(raw) < 4 * 1024**2
            value = json.loads(raw)
            if name == 'windows-development.json':
                assert value['github']['run_id'] == run and value['github']['run_attempt'] == 1
                assert value['github']['workflow_sha'] == '55b511a82ad9c2cce57d9d5cf01a3bfc741c1250'
                assert value['base_commit'] == '6d037bcbba376d2b2e6e53caa0f96874ac1497ef'
                assert value['bootstrap_sha256'] == '80517ea1faf16cfa1759691321b5ed7dacf95cb94b1f46254eb674faf162f87f'
                assert value['patch_manifest_sha256'] == '5e2c48b39d85df1bb530d1cf6e5e487cf0e81d97e537a0ccbaf578fc685db649'
                value['steps'] = [{k: row.get(k) for k in ('label', 'exit_code', 'duration_seconds')} for row in value.get('steps', [])]
                value = {key: value.get(key) for key in ('status', 'github', 'check', 'build',
                    'source_sha256', 'source_sha256_after', 'started_at', 'finished_at', 'steps')}
            item['files'][name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'value': value}
        for name in ('10-host-tests.log', '11-tools-tests.log', '18-gradle.log', 'linux-backend-full-suite.log'):
            path = state / name
            if not path.is_file() or path.is_symlink():
                continue
            with path.open('rb') as stream:
                stream.seek(max(0, path.stat().st_size - 24000))
                lines = stream.read().decode('utf-8', errors='replace').splitlines()
            item['log_tail'][name] = [line[:700] for line in lines if len(line) < 1000 and
                re.search(r'Ran \d+ tests?|^OK\b|FAILED|BUILD SUCCESSFUL|BUILD FAILED|passed|^> Task|^e:', line)][-12:]
        result['build'].append(item)
    folder = runner / ('omni-cio-gateway/omni-cio-gateway/windows-development-' + str(run) + '-1/app/build/test-results/testDebugUnitTest')
    if folder.is_dir():
        suites = []
        for path in sorted(folder.glob('TEST-*.xml')):
            assert path.is_file() and not path.is_symlink() and path.stat().st_size < 4 * 1024**2
            raw = path.read_bytes()
            node = ET.fromstring(raw)
            suites.append({'name': path.name, 'sha256': hashlib.sha256(raw).hexdigest(),
                **{key: int(node.get(key, '0')) for key in ('tests', 'failures', 'errors', 'skipped')},
                'failures_details': [{'case': case.get('name'), 'type': failure.get('type'),
                    'message': failure.get('message', '')[:1200]}
                    for case in node.findall('testcase') for failure in case.findall('failure')][:8]})
        result['jvm'].append({'path': str(folder), 'suites': suites,
            'totals': {key: sum(s[key] for s in suites) for key in ('tests', 'failures', 'errors', 'skipped')}})
print('N00_RESUME_OBSERVATION=' + json.dumps(result, ensure_ascii=True))
