"""Hosted verification after the exact remote publication payload returns."""
# api/with_ams/p and remote are provided by the reviewed generated workflow.
output = with_ams(remote, timeout=240, capture=True).decode('utf-8')
assert len(output.encode()) <= 65536
receipt_lines = [line.split('=', 1)[1] for line in output.splitlines() if line.startswith('OWNER_PREVIEW48_DELIVERY=')]
client_lines = [line.split('=', 1)[1] for line in output.splitlines() if line.startswith('OWNER_PREVIEW48_CLIENT_OBSERVATIONS=')]
assert len(receipt_lines) == len(client_lines) == 1
receipt = json.loads(receipt_lines[0])
observations = json.loads(client_lines[0])
assert receipt['version_code'] == 48 and receipt['version_name'] == '0.14.1-preview'
assert receipt['apk_sha256'] == '85fb8b3c3e0020080a421efaae1c101df0e55f97bacb791064e1b1cbaa4a8df1'
assert receipt['apk_bytes'] == 29937843
assert receipt['certificate_sha256'] == 'bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1'
assert receipt['source_sha256'] == '26d1ccf6b9685925291edb968f17ef091b145831d7c6ca791e5e942246af49fa'
assert receipt['source_backup_commit'] == 'fd2a307220158b0fc2055cfb0eb4fd9fc51d8d4b'
assert receipt['full_check_and_build_passed'] is True
assert receipt['previous_version'] == 47 and receipt['previous_apk_sha256'] == '1f699684618f44f1da4c71f3fa19bbf9125e906ab431865747cf44e0b5ea0602'
assert receipt['build_report_sha256'] == '3d0d4f59f709054469cefa274f3bb92d7ba840d10a5f9a2e68bcdc77d535c72f'
assert receipt['source_archive_sha256'] == '2c6ef4e2f6f176d237f97871ced48d9ab7b22a20486f2c852c5e25d7abfcfa62'
assert receipt['source_archive_bytes'] == 69697259
assert receipt['preview_install_smoke'] == {'status': 'not_executed_for_published_build', 'run_id': None, 'full_runtime_matrix_passed': False, 'physical_phone_verified': False}
assert receipt['runtime_pass'] is receipt['phone_verified'] is receipt['complete_release_gate_passed'] is False
assert observations['physical_phone_verified'] is False and observations['client_headers_are_not_device_attestation'] is True
origin = 'https://analyst-ai-2941515.twc1.net'
expected_path = '/client/apk/Analyst-AI-48-' + receipt['apk_sha256'] + '.apk'
assert receipt['url'] == origin + expected_path
opener = urllib.request.build_opener(p.NoRedirect(), urllib.request.HTTPSHandler(context=p.verified_ssl_context()))
policy_url = origin + '/client/update-policy?package_name=ru.omnicio.app.debug'

def public_json(url, limit):
    with opener.open(urllib.request.Request(url, headers={'Cache-Control': 'no-cache'}), timeout=45) as response:
        assert response.status == 200 and response.headers.get_content_type() == 'application/json'
        raw = response.read(limit + 1)
        assert len(raw) <= limit
        return json.loads(raw)

def checked_policy():
    policy = public_json(policy_url, 16384)
    for key in ('version_code', 'version_name', 'apk_sha256', 'apk_bytes', 'certificate_sha256', 'published_at'):
        assert type(policy[key]) is type(receipt[key]) and policy[key] == receipt[key]
    assert policy['package_name'] == 'ru.omnicio.app.debug' and policy['min_sdk'] == 37
    assert policy['minimum_version_code'] == 48 and policy['version_is_not_attestation'] is True
    assert policy['apk_path'] == expected_path
    return policy

policy = checked_policy()
digest = hashlib.sha256()
size = 0
with opener.open(urllib.request.Request(receipt['url'], headers={'Cache-Control': 'no-cache'}), timeout=120) as response:
    assert response.status == 200
    assert response.headers.get_content_type() == 'application/vnd.android.package-archive'
    declared = response.headers.get('Content-Length')
    if declared is not None:
        assert declared == str(receipt['apk_bytes'])
    for block in iter(lambda: response.read(1024**2), b''):
        size += len(block)
        assert size <= receipt['apk_bytes']
        digest.update(block)
assert size == receipt['apk_bytes'] and digest.hexdigest() == receipt['apk_sha256']
assert checked_policy() == policy
assert public_json(origin + '/health', 1024) == {'status': 'ok'}
verification = {
    'schema': 1, 'kind': 'owner_preview48_public_delivery',
    'publication': receipt, 'client_observations_at_publication': observations,
    'https_policy_verified': True, 'https_entire_apk_download_verified': True,
    'https_apk_bytes': size, 'https_apk_sha256': digest.hexdigest(),
    'backend_health_http': 200, 'backend_health_body': {'status': 'ok'},
    'physical_phone_verified': False, 'complete_release_gate_passed': False,
}
out = pathlib.Path(os.environ['RUNNER_TEMP']) / 'owner-preview48-public-verification.json'
with out.open('x', encoding='utf-8') as target:
    json.dump(verification, target, ensure_ascii=False, sort_keys=True, indent=2)
    target.write('\n')
print('OWNER_PREVIEW48_PUBLIC_VERIFIED=' + json.dumps(verification, ensure_ascii=True), flush=True)
