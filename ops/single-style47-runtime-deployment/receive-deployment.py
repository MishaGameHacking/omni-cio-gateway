"""Hosted action: validate GitHub/build/source binding before remote mutation."""
# The pinned administrative SSH prefix, EXPECTED, SOURCE_FILES and remote are
# injected by prepare-deployment.py. No application module is imported here.
import re
import stat


def need(value, code):
    if not value:
        raise RuntimeError(code)


def source_backup_verified():
    root = pathlib.Path('source-backup47').absolute()
    need(root.resolve(strict=True) == root and root.is_dir(), 'source_backup_checkout_not_canonical')

    def git(*args):
        result = subprocess.run(['git', '-C', str(root), *args], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30, check=False)
        need(result.returncode == 0 and len(result.stdout) <= 4 * 1024**2, 'source_backup_git_unavailable')
        return result.stdout

    need(git('rev-parse', 'HEAD').decode().strip() == EXPECTED['source_backup_commit'], 'source_backup_head_changed')
    entries = git('ls-tree', '-r', '-z', '--full-tree', 'HEAD').split(b'\0')
    observed = {}
    for entry in entries:
        if not entry:
            continue
        left, raw_name = entry.split(b'\t', 1)
        mode, kind, blob = left.split(b' ')
        name = raw_name.decode('utf-8')
        if name in ('AGENTS.md', 'README.md') or name.startswith('docs/'):
            continue
        need(name in SOURCE_FILES and mode in (b'100644', b'100755') and kind == b'blob'
             and name not in observed, 'source_backup_file_set_changed')
        path = root / name
        need(path.resolve(strict=True) == path, 'linked_source_backup_file')
        for parent in path.parents:
            need(not parent.is_symlink(), 'linked_source_backup_parent')
            if parent == root:
                break
        info = path.lstat()
        need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size == SOURCE_FILES[name]['bytes']
             and info.st_size <= 128 * 1024**2, 'source_backup_file_size_changed')
        raw = path.read_bytes()
        identity = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        need(identity == SOURCE_FILES[name] and hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
             == blob.decode('ascii'), 'source_backup_bytes_not_built_source')
        observed[name] = identity
    need(observed == SOURCE_FILES, 'source_backup_code_inventory_changed')
    digest = hashlib.sha256()
    for name, item in sorted(observed.items(), key=lambda row: row[0].encode('utf-8')):
        digest.update(name.encode('utf-8') + b'\0' + item['sha256'].encode('ascii') + b'\0')
    need(digest.hexdigest() == EXPECTED['source_sha256'], 'source_backup_inventory_hash_changed')
    return {'head': EXPECTED['source_backup_commit'], 'source_sha256': digest.hexdigest(), 'code_files': len(observed)}


def successful_build_workflow():
    opener = urllib.request.build_opener(p.NoRedirect(), urllib.request.HTTPSHandler(context=p.verified_ssl_context()))
    run, attempt = EXPECTED['github']['run_id'], EXPECTED['github']['run_attempt']
    prefix = 'https://api.github.com/repos/MishaGameHacking/omni-cio-gateway/actions/runs/' + str(run)

    def read(url):
        request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + os.environ['GH_READ_TOKEN'],
            'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'})
        with opener.open(request, timeout=20) as response:
            need(response.status == 200, 'github_build_read_failed')
            raw = response.read(2 * 1024**2 + 1)
        need(len(raw) <= 2 * 1024**2, 'github_build_response_too_large')
        return json.loads(raw)

    current = read(prefix)
    specific = read(prefix + '/attempts/' + str(attempt))
    for row in (current, specific):
        need(row['id'] == run and row['run_attempt'] == attempt and row['status'] == 'completed' and
             row['conclusion'] == 'success' and row['head_sha'] == EXPECTED['github']['workflow_sha'] and
             row['path'] == '.github/workflows/windows-development.yml' and row['event'] == 'push' and
             row['head_branch'] == 'codex/timeweb-owner-prepare-2026-10-23', 'exact_full_windows_workflow_not_successful')
    jobs = read(prefix + '/attempts/' + str(attempt) + '/jobs?per_page=10')
    need(jobs['total_count'] == len(jobs['jobs']) == 5 and all(row['status'] == 'completed' and
         row['conclusion'] == 'success' and row['run_id'] == run for row in jobs['jobs']),
         'all_five_windows_jobs_must_pass')
    return {'run_id': run, 'run_attempt': attempt, 'workflow_sha': EXPECTED['github']['workflow_sha'],
            'successful_jobs': 5, 'current_attempt_verified': True}


need(__debug__ and os.environ['GITHUB_REPOSITORY'] == 'MishaGameHacking/omni-cio-gateway' and
     os.environ['GITHUB_REF'] == 'refs/heads/codex/timeweb-owner-prepare-2026-10-23' and
     os.environ['GITHUB_EVENT_NAME'] == 'push', 'unexpected_administrative_workflow_context')
run, attempt = os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT']
need(re.fullmatch('[0-9]{8,20}', run) and re.fullmatch('[0-9]{1,5}', attempt), 'invalid_administrative_run_identity')
need(hashlib.sha256(remote.encode('utf-8')).hexdigest() == REMOTE_SHA256, 'remote_payload_changed')
workflow_verified = successful_build_workflow()
backup_verified = source_backup_verified()
before = public_check()
raw = with_ams(remote, timeout=600, capture=True)
need(0 < len(raw) <= 32768, 'remote_receipt_outside_bound')
receipt = json.loads(raw)
folder = pathlib.Path(os.environ['RUNNER_TEMP']).resolve(strict=True) / ('single_style47-web-deployment-' + run + '-' + attempt)
folder.mkdir(exist_ok=False)


def save(name, value):
    data = (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + '\n').encode('ascii')
    need(len(data) <= 65536 and name in {'deployment.json', 'verification.json', 'failure.json'}, 'unsafe_receipt_output')
    with (folder / name).open('xb') as output:
        output.write(data)


if receipt.get('kind') == 'single_style47_web_deployment_failure':
    need(set(receipt) == {'schema', 'kind', 'code'} and receipt['schema'] == 1 and
         re.fullmatch('[a-z_]{1,100}', receipt['code']), 'invalid_remote_failure_schema')
    save('failure.json', receipt)
    print('SINGLE_STYLE47_WEB_DEPLOYMENT_FAILURE=' + json.dumps(receipt), flush=True)
    raise RuntimeError('Remote web deployment failed; inspect the bounded failure receipt')
need(receipt['schema'] == 1 and receipt['kind'] == 'single_style47_exact_three_file_web_deployment' and
     receipt['status'] in {'deployed_verified', 'already_deployed_verified'} and
     receipt['runtime_server_id'] == 9417611 and receipt['public_host'] == PUBLIC_HOST and
     receipt['source_sha256'] == EXPECTED['source_sha256'] and
     receipt['source_backup_commit'] == EXPECTED['source_backup_commit'] and
     receipt['archive'] == EXPECTED['archive'] and receipt['build_report'] == EXPECTED['build_report'] and
     receipt['web_sources'] == {name: row['new'] for name, row in EXPECTED['web_sources'].items()},
     'remote_deployment_identity_changed')
need(receipt['full_windows_check_and_build_passed'] is True and
     receipt['actual_html_test_evidence']['original_html_test_count'] == 6 and
     receipt['normal_owner_startup_has_possible_database_effects'] is True,
     'wrong_remote_validation_scope')
for key in ('other_services_restarted_by_deployer', 'caddy_or_service_configuration_changed',
            'database_or_environment_files_opened_by_deployer', 'help_deployed', 'dependencies_changed',
            'apk_published_or_installed', 'trading_or_model_routes_called',
            'physical_phone_verified', 'full_android_runtime_matrix_passed'):
    need(receipt[key] is False, 'remote_scope_widened')
save('deployment.json', receipt)
after = public_check(expected_style=EXPECTED['callback_style_sha256'], expected_policy=before['update_policy_sha256'])
need(receipt['public']['update_policy_sha256'] == after['update_policy_sha256'] and
     receipt['public']['callback_style_sha256'] == after['callback_style_sha256'] and
     receipt['public']['callback_theme_verified'] is True, 'independent_public_verification_differs')
verification = {'schema': 1, 'kind': 'single_style47_three_file_public_verification', 'deployment': receipt,
                'github_build': workflow_verified, 'source_backup': backup_verified,
                'independent_public': after, 'server9417611_verified_by_pinned_transport': True,
                'login_start_called': False, 'owner_denial_forced': False, 'help_route_added': False,
                'physical_phone_verified': False, 'full_android_runtime_matrix_passed': False}
save('verification.json', verification)
print('SINGLE_STYLE47_WEB_PUBLIC_VERIFIED=' + json.dumps(verification, ensure_ascii=True, sort_keys=True), flush=True)
