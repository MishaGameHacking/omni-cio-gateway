"""Bind a server bundle to one successful laptop run before existing SSH transport."""
import hashlib
import json
import os
from pathlib import Path
import re
import zipfile

BASE = 'cc22cb7ee3fe82eca28e4162e13c4463cab5ddc4'
MODULES = {'volume_chat.py', 'investment_chat_policy.py',
                     'ai_guarded_client.py', 'volume_jobs.py', 'order_lifecycle.py'}


def require(value, code):
    if not value:
        raise RuntimeError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify_artifact(archive, *, archive_sha, bundle_sha, source_sha, run_id):
    require(re.fullmatch('[a-f0-9]{40}', source_sha) and source_sha != '0' * 40,
            'source_identity_unset')
    require(re.fullmatch('[0-9]{8,20}', run_id), 'run_identity_unset')
    require(all(re.fullmatch('[a-f0-9]{64}', item) and item != '0' * 64
                for item in (archive_sha, bundle_sha)), 'artifact_identity_unset')
    require(archive.stat().st_size <= 32 * 1024**2, 'artifact_size_invalid')
    require(sha(archive.read_bytes()) == archive_sha, 'artifact_digest_changed')
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        require(len(entries) <= 50 and sum(row.file_size for row in entries) <= 32 * 1024**2,
                'artifact_size_invalid')
        bundles = [row for row in entries if Path(row.filename).name == 'server-runtime.json']
        reports = [row for row in entries if Path(row.filename).name == 'windows-backend-report.json']
        require(len(bundles) == len(reports) == 1, 'ambiguous_artifact')
        data, report_bytes = zipped.read(bundles[0]), zipped.read(reports[0])
    require(sha(data) == bundle_sha, 'bundle_digest_changed')
    bundle, report = json.loads(data), json.loads(report_bytes)
    require(bundle['schema'] == 1 and bundle['base_commit'] == BASE
            and bundle['apk_changed'] is False and set(bundle['files']) == MODULES,
            'release_scope_changed')
    require(bundle['source_commit'] == report['tested_merge_sha'] == source_sha
            and bundle['run_id'] == run_id and bundle['run_attempt'] == '1'
            and bundle['host'] == report['host'] == 'LAPTOP-NPSGA016'
            and report['status'] == report['linux']['status'] == 'passed'
            and report['linux']['changed_sources'] == []
            and bundle['source_sha256'] == report['complete_source_sha256']
            and bundle['verification_sha256'] == sha(report_bytes),
            'exact_laptop_verification_required')
    return data


def main():
    data = verify_artifact(Path(os.environ['RUNNER_TEMP']) / 'server-runtime-artifact.zip',
        archive_sha=os.environ['EXPECTED_ARTIFACT_SHA256'], bundle_sha=os.environ['EXPECTED_BUNDLE_SHA256'],
        source_sha=os.environ['EXPECTED_SOURCE_SHA'], run_id=os.environ['EXPECTED_TEST_RUN'])
    destination = Path('deploy/plan-20261027')
    require(destination.is_dir() and not destination.is_symlink(), 'transport_directory_missing')
    (destination / 'payload.json').write_bytes(data)
    (destination / 'operation.py').write_bytes(Path('deploy/chat_reliability_release.py').read_bytes())
    print(json.dumps({'source_commit': os.environ['EXPECTED_SOURCE_SHA'],
                      'test_run': os.environ['EXPECTED_TEST_RUN'], 'bundle_sha256': sha(data)}))


if __name__ == '__main__':
    main()
