"""Extract verified Windows source bytes and test them on the laptop's Linux filesystem."""
import hashlib, json, os, pathlib, subprocess, sys, tarfile, time, zipfile

assert sys.platform == 'linux' and os.getuid() >= 1000
archive, archive_hash, manifest_path, manifest_hash, location, export_path = sys.argv[1:]
assert hashlib.sha256(pathlib.Path(archive).read_bytes()).hexdigest() == archive_hash
manifest_bytes = pathlib.Path(manifest_path).read_bytes()
assert hashlib.sha256(manifest_bytes).hexdigest() == manifest_hash
manifest = json.loads(manifest_bytes)
root = pathlib.Path(location)
assert root.parent == pathlib.Path('/opt/analyst-ci/runs') and not root.exists()
root.mkdir()
source, evidence = root / 'checkout', root / 'evidence'
source.mkdir()
evidence.mkdir()
identities = {r['path']: r for r in manifest['files']}
assert len(identities) == len(manifest['files'])
with tarfile.open(archive) as tar:
    assert set(tar.getnames()) == set(identities)
    for member in tar:
        rel = pathlib.PurePosixPath(member.name)
        assert member.isfile() and not rel.is_absolute() and '..' not in rel.parts
        data = tar.extractfile(member).read()
        row = identities[member.name]
        assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']
        target = source / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(0o644)

env = {'PATH': '/usr/bin:/bin', 'HOME': '/home/analyst-ci', 'LANG': 'C.UTF-8', 'PYTHONUNBUFFERED': '1',
       'TELEGRAM_CLIENT_ID': '123456', 'TELEGRAM_CLIENT_SECRET': 'test-only', 'BACKEND_PUBLIC_URL': 'https://example.invalid',
       'TELEGRAM_REDIRECT_URI': 'https://example.invalid/auth/telegram/callback',
       'FERNET_KEY': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=', 'DATABASE_PATH': str(root / 'tests.sqlite3'),
       'ANALYSIS_SCHEDULER_ENABLED': 'false', 'AI_EXTERNAL_PROCESSING_APPROVED': 'false',
       'PIP_CONFIG_FILE': '/dev/null', 'PIP_DISABLE_PIP_VERSION_CHECK': '1'}
report = {'source_sha256': manifest['source_sha256'], 'platform': sys.platform, 'python': sys.version, 'uid': os.getuid(), 'steps': []}

def run(name, args, timeout=900):
    print('LINUX_GUEST_STEP=' + name, flush=True)
    target = evidence / (name + '.log')
    started = time.monotonic()
    with target.open('xb') as out:
        result = subprocess.run(args, cwd=source, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, timeout=timeout)
    row = {'name': name, 'exit_code': result.returncode, 'seconds': round(time.monotonic()-started, 3),
           'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    report['steps'].append(row)
    print('LINUX_GUEST_RESULT=' + json.dumps(row), flush=True)
    print(target.read_text(errors='replace')[-9000:], flush=True)
    if result.returncode:
        raise RuntimeError('Linux test failed: ' + name)

try:
    venv = root / 'venv'
    py = str(venv / 'bin/python')
    run('venv', [sys.executable, '-m', 'venv', str(venv)], 120)
    run('requirements', [py, '-m', 'pip', '--require-virtualenv', 'install', '--no-input', '--index-url', 'https://pypi.org/simple', '-r', 'backend/requirements-dev.txt'])
    run('dependencies', [py, '-m', 'pip', 'check'])
    run('dependency-versions', [py, '-m', 'pip', 'freeze', '--all'])
    run('compile-backend', [py, '-m', 'compileall', '-q', 'backend'])
    run('backend-full-suite', [py, '-m', 'pytest', 'backend/tests', '-q', '--junitxml=' + str(evidence / 'backend-tests.xml')], 1200)
    smoke = "from fastapi.testclient import TestClient; from backend.app import app; client=TestClient(app); client.__enter__(); response=client.get('/health'); assert response.status_code==200 and response.json()=={'status':'ok'}; assert client.get('/openapi.json').status_code==200; client.__exit__(None,None,None); print('HEALTH_OPENAPI=passed')"
    run('health-openapi', [py, '-c', smoke], 120)
    report['status'] = 'passed'
except BaseException as error:
    report.update(status='failed', error_type=type(error).__name__, error=str(error)[:400])
    raise
finally:
    changed = [name for name, row in identities.items() if not (source/name).is_file() or hashlib.sha256((source/name).read_bytes()).hexdigest() != row['sha256']]
    report['changed_sources'] = changed
    if changed:
        report['status'] = 'failed_integrity'
    (evidence / 'linux-test-report.json').write_text(json.dumps(report, indent=2))
    with zipfile.ZipFile(export_path, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for path in evidence.iterdir():
            z.write(path, path.name)
    print('LINUX_TEST_REPORT=' + json.dumps(report), flush=True)
    if changed:
        raise RuntimeError('Source files changed during Linux checks')
