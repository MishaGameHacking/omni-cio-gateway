"""Verify the exact successful laptop artifact before the existing SSH transport."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import zipfile


def main():
    archive = Path(os.environ['RUNNER_TEMP']) / 'server-runtime-artifact.zip'
    raw = archive.read_bytes()
    if hashlib.sha256(raw).hexdigest() != os.environ['EXPECTED_ARTIFACT_SHA256']:
        raise RuntimeError('artifact_digest_mismatch')
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        if len(entries) > 50 or sum(row.file_size for row in entries) > 32 * 1024 * 1024:
            raise RuntimeError('invalid_artifact_size')
        bundles = [row for row in entries if Path(row.filename).name == 'server-runtime.json']
        reports = [row for row in entries if Path(row.filename).name == 'windows-backend-report.json']
        if len(bundles) != 1 or len(reports) != 1:
            raise RuntimeError('ambiguous_artifact')
        data = zipped.read(bundles[0])
        report_bytes = zipped.read(reports[0])
    if hashlib.sha256(data).hexdigest() != os.environ['EXPECTED_BUNDLE_SHA256']:
        raise RuntimeError('release_bundle_digest_mismatch')
    bundle, report = json.loads(data), json.loads(report_bytes)
    expected = os.environ['EXPECTED_SOURCE_SHA']
    if not (bundle['source_commit'] == report['tested_merge_sha'] == expected
            and bundle['run_id'] == os.environ['EXPECTED_TEST_RUN']
            and bundle['run_attempt'] == '1' and report['status'] == 'passed'
            and report['linux']['status'] == 'passed'
            and report['linux']['changed_sources'] == []
            and bundle['source_sha256'] == report['complete_source_sha256']
            and bundle['verification_sha256'] == hashlib.sha256(report_bytes).hexdigest()):
        raise RuntimeError('release_not_bound_to_exact_laptop_verification')
    destination = Path('deploy/plan-20261027')
    (destination / 'payload.json').write_bytes(data)
    shutil.copyfile('deploy/investment_osint_release.py', destination / 'operation.py')
    print(json.dumps({'source_commit': expected, 'test_run': bundle['run_id'],
                      'verified_bundle': hashlib.sha256(data).hexdigest()}))


if __name__ == '__main__':
    main()
