"""Synthetic artifacts verify publication gates, not an Android installation."""
from copy import deepcopy
import hashlib

import pytest

from backend.client_updates import ReleaseChannel, ReleaseUnavailable
from backend.installation_evidence import from_ci_reports
from backend.release_publication import publish
from backend.tests.test_installation_evidence import CANDIDATE, android15_report, reports, runtime_reports

PACKAGE = 'ru.omnicio.app.debug'
CERTIFICATE = 'c' * 64


def publication_report(apk, version, transcripts, *, minimum=35):
    digest = hashlib.sha256(apk.read_bytes()).hexdigest()
    transcripts = deepcopy(transcripts)
    for run in transcripts:
        for record in run['results']:
            if record.get('apk_sha256') == CANDIDATE:
                record['apk_sha256'] = digest
    return {'package': PACKAGE, 'version_code': version, 'version_name': f'test-{version}',
            'min_sdk': minimum, 'sha256': digest, 'bytes': apk.stat().st_size,
            'certificate_sha256': CERTIFICATE, 'signature_v2': True, 'zipalign_16kb': True,
            'debuggable': False, 'test_only': False, 'installation_tests': transcripts,
            'installation_evidence': from_ci_reports(transcripts, digest)}


def test_version34_transcript_remains_publishable_without_runtime_page_measurement(tmp_path):
    apk = tmp_path / 'synthetic.apk'
    apk.write_bytes(b'legacy publication gate fixture, not an APK')
    report = publication_report(apk, 34, [android15_report(), *reports()])
    result = publish(tmp_path / 'releases', apk, report, expected_certificate=CERTIFICATE, now=100)
    assert result.version_code == 34
    assert result.min_sdk == 35


def test_version35_requires_and_accepts_both_exact_runtime_installations(tmp_path):
    apk = tmp_path / 'synthetic.apk'
    apk.write_bytes(b'new publication gate fixture, not an APK')
    report = publication_report(apk, 35, runtime_reports())
    result = publish(tmp_path / 'releases', apk, report, expected_certificate=CERTIFICATE, now=100)
    assert result.version_code == 35
    assert ReleaseChannel(tmp_path / 'releases').current(PACKAGE) == result


@pytest.mark.parametrize('failure', ['missing_transcript', 'legacy_transcript', 'wrong_runtime_size', 'missing_profile'])
def test_runtime_evidence_failure_preserves_previously_published_version(tmp_path, failure):
    apk = tmp_path / 'synthetic.apk'
    root = tmp_path / 'releases'
    apk.write_bytes(b'previous synthetic publication')
    previous = publish(root, apk, publication_report(apk, 34, [android15_report(), *reports()]),
                       expected_certificate=CERTIFICATE, now=100)
    apk.write_bytes(b'candidate synthetic publication')
    report = publication_report(apk, 35, runtime_reports(), minimum=36)
    if failure == 'missing_transcript':
        del report['installation_tests']
    elif failure == 'legacy_transcript':
        report = publication_report(apk, 35, [android15_report(), *reports()])
    elif failure == 'wrong_runtime_size':
        run = report['installation_tests'][0]
        next(row for row in run['results'] if row['test'] == 'kernel_page_size')['page_size_bytes'] = 4096
    else:
        run = report['installation_tests'][0]
        run['results'] = [row for row in run['results'] if row['test'] != 'profile_ui']
    with pytest.raises(ReleaseUnavailable):
        publish(root, apk, report, expected_certificate=CERTIFICATE, now=200)
    assert ReleaseChannel(root).current(PACKAGE) == previous
