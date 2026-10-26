"""Prepare a read-only source/service observation for the existing owner runtime."""
from pathlib import Path
import ast
import hashlib
import json
import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'mandate48-runtime-observation'
TARGET = '.github/workflows/portfolio-mandate48-runtime-observation.yml'


def main():
    source = ROOT / 'theme46-runtime-routing/prepared/observe-routes.py'
    raw = source.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '79c73c55a07e5a96f92c84ad89982dd84a3655598b64a90d774b28781bcca177'
    text = raw.decode()
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    entry = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    prefix = ''.join(lines[:entry.lineno - 1])
    assignment = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'EXPECTED' for t in n.targets))
    old = ''.join(lines[assignment.lineno - 1:assignment.end_lineno])
    baseline = json.loads((ROOT / 'build47-v20/source-final.json').read_bytes())
    names = sorted(name for name in baseline['files'] if name.startswith('backend/') and name.endswith('.py') and len(Path(name).parts) == 2)
    assert 30 < len(names) < 300
    expected = ast.literal_eval(assignment.value)
    expected['sources'] = {'/opt/analyst-ai/' + name: baseline['files'][name] for name in names}
    expected['sources']['/opt/analyst-ai/backend/portfolio_mandate.py'] = None
    for name in ('/opt/analyst-ai-updates/backend/public_updates_app.py', '/opt/analyst-ai-updates/backend/release_delivery.py'):
        # Preserve separately deployed public-update entrypoints from the original observation.
        previous = ast.literal_eval(assignment.value)['sources']
        if name in previous:
            expected['sources'][name] = previous[name]
    prefix = prefix.replace(old, 'EXPECTED = ' + repr(expected) + '\n', 1)
    remote = prefix + '''def main():
    need(sys.platform == 'linux' and os.geteuid() == 0, 'wrong_observer_platform')
    sources = {}
    for name, expected in EXPECTED['sources'].items():
        path = Path(name)
        try:
            path.lstat()
        except FileNotFoundError:
            sources[name] = {'status': 'absent', 'matches_reference47': expected is None}
            continue
        metadata, raw = observed_file(path, 2 * 1024**2)
        if raw is not None:
            metadata['matches_reference47'] = identity(raw) == expected
        sources[name] = metadata
    services = {name: service_observation(name) for name in SERVICES}
    caddy, _ = active_caddy()
    config, _ = observed_file(Path('/etc/caddy/Caddyfile'), 128 * 1024)
    connection = http.client.HTTPConnection('127.0.0.1', 8080, timeout=5)
    try:
        connection.request('GET', '/health')
        response = connection.getresponse()
        body = response.read(1025)
        need(response.status == 200 and len(body) <= 1024 and json.loads(body) == {'status': 'ok'}, 'owner_health_failed')
    finally:
        connection.close()
    result = {'schema': 1, 'kind': 'portfolio_mandate48_runtime_readonly',
        'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'runtime_server_id': 9417611, 'public_host': PUBLIC_HOST,
        'sources': sources, 'services': services, 'active_caddy_configuration': caddy,
        'caddy_file': config, 'local_health_status': 200,
        'application_imported': False, 'application_or_tests_executed': False,
        'environment_file_or_database_read': False, 'source_or_configuration_text_exported': False,
        'runtime_files_written': False, 'services_restarted': False,
        'private_app_routes_requested': False, 'model_or_broker_calls': False}
    raw = (json.dumps(result, sort_keys=True) + '\\n').encode()
    need(len(raw) <= 128 * 1024, 'observation_exceeds_bound')
    sys.stdout.buffer.write(raw)


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        code = str(error) if isinstance(error, ObservationError) else type(error).__name__
        if re.fullmatch(r'[A-Za-z0-9_]{1,100}', code) is None:
            code = 'mandate_runtime_observation_failed'
        print('MANDATE48_OBSERVATION_FAILED=' + code, file=sys.stderr, flush=True)
        raise SystemExit(1) from None
'''
    transport = (ROOT / 'design47/free-runtime/hosted-observer.py').read_text().split('REMOTE_SHA256 = ', 1)[0]
    hosted = transport + 'REMOTE_SHA256 = ' + repr(hashlib.sha256(remote.encode()).hexdigest()) + '\nremote = ' + repr(remote) + '''
assert __debug__ and os.environ['GITHUB_REPOSITORY'] == 'MishaGameHacking/omni-cio-gateway'
assert os.environ['GITHUB_REF'] == 'refs/heads/codex/timeweb-owner-prepare-2026-10-23'
assert hashlib.sha256(remote.encode()).hexdigest() == REMOTE_SHA256
raw = with_ams(remote, timeout=120, capture=True)
assert 0 < len(raw) <= 128 * 1024
value = json.loads(raw)
assert value['kind'] == 'portfolio_mandate48_runtime_readonly' and value['runtime_server_id'] == 9417611
for name in ('application_imported', 'application_or_tests_executed', 'environment_file_or_database_read',
             'source_or_configuration_text_exported', 'runtime_files_written', 'services_restarted',
             'private_app_routes_requested', 'model_or_broker_calls'):
    assert value[name] is False
folder = pathlib.Path(os.environ['RUNNER_TEMP']) / ('mandate48-runtime-observation-' + os.environ['GITHUB_RUN_ID'])
folder.mkdir(exist_ok=False)
(folder / 'runtime-observation.json').write_bytes(raw)
print('MANDATE48_RUNTIME=' + json.dumps(value, sort_keys=True), flush=True)
'''
    ast.parse(remote)
    ast.parse(hosted)
    workflow = yaml.safe_load((ROOT / 'design47/free-runtime/workflow.yml').read_bytes())
    workflow['name'] = 'Read existing owner runtime source identities before mandate48 deployment'
    workflow['on']['push']['paths'] = [TARGET]
    workflow['concurrency']['group'] = 'owner-preview-release-publication'
    steps = workflow['jobs']['observe']['steps']
    steps[1]['name'] = 'Observe only allowlisted source hashes, service bindings and health'
    steps[1]['run'] = "python - <<'PY'\n" + hosted + '\nPY\n'
    steps[2]['name'] = 'Retain original read-only runtime evidence'
    steps[2]['with']['name'] = 'mandate48-runtime-observation'
    steps[2]['with']['path'] = '${{ runner.temp }}/mandate48-runtime-observation-${{ github.run_id }}/*.json'
    output = yaml.safe_dump(workflow, allow_unicode=True, sort_keys=False, width=120)
    assert yaml.safe_load(output) == workflow
    OUT.mkdir(exist_ok=False)
    for name, content in [('observe-runtime.py', remote), ('hosted-observer.py', hosted), ('workflow.yml', output)]:
        (OUT / name).write_text(content)
    entries = [{'path': TARGET, 'mode': '100644', 'type': 'blob', 'content': output}]
    for path in [Path(__file__), OUT / 'observe-runtime.py', OUT / 'hosted-observer.py']:
        entries.append({'path': 'ops/portfolio-mandate48-runtime-observation/' + path.name,
                        'mode': '100644', 'type': 'blob', 'content': path.read_text()})
    result = json.dumps(entries, ensure_ascii=False)
    (OUT / 'tree-elements.json').write_text(result)
    print(json.dumps({'prepared_only': True, 'sources': len(expected['sources']), 'entries_characters': len(result),
                      'entries_sha256': hashlib.sha256(result.encode()).hexdigest()}))


if __name__ == '__main__':
    main()
