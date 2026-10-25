"""Synthetic artifacts verify publication gates, never an Android installation."""
from copy import deepcopy
import hashlib

import pytest

from backend.client_updates import ReleaseChannel, ReleaseUnavailable
from backend.installation_evidence import from_ci_reports
from backend.release_publication import publish
from backend.tests.android_runtime_fixtures import runtime_reports

PACKAGE = 'ru.omnicio.app.debug'
CERTIFICATE = 'c' * 64


def publication_report(apk, version):
    digest = hashlib.sha256(apk.read_bytes()).hexdigest()
    transcripts = runtime_reports(digest)
    return {'package': PACKAGE, 'version_code': version, 'version_name': f'test-{version}',
            'min_sdk': 37, 'target_sdk': 37, 'sha256': digest, 'bytes': apk.stat().st_size,
            'certificate_sha256': CERTIFICATE, 'signature_v2': True, 'zipalign_16kb': True,
            'debuggable': False, 'test_only': False, 'installation_tests': transcripts,
            'installation_evidence': from_ci_reports(transcripts, digest, version_code=version)}


@pytest.mark.parametrize('version', [34, 35])
def test_every_version_requires_and_accepts_both_current_runtime_installations(tmp_path, version):
    apk = tmp_path / 'synthetic.apk'
    apk.write_bytes(b'synthetic publication gate fixture, not an APK')
    report = publication_report(apk, version)
    result = publish(tmp_path / 'releases', apk, report, expected_certificate=CERTIFICATE, now=100)
    assert result.version_code == version
    assert result.min_sdk == 37
    assert ReleaseChannel(tmp_path / 'releases').current(PACKAGE) == result


def change_evidence(report, failure):
    if failure == 'missing_transcript':
        del report['installation_tests']
    elif failure == 'unsupported_os':
        report['installation_tests'][0]['android_api'] = 36
    elif failure == 'wrong_runtime_size':
        rows = report['installation_tests'][0]['results']
        next(row for row in rows if row['test'] == 'kernel_page_size')['page_size_bytes'] = 16384
    elif failure == 'missing_profile':
        run = report['installation_tests'][0]
        run['results'] = [row for row in run['results'] if row['test'] != 'profile_ui']
    elif failure == 'duplicate_runtime':
        report['installation_tests'][1] = deepcopy(report['installation_tests'][0])
    else:
        report['installation_evidence'] = {'apk_sha256': report['sha256'], '36': {'launch': True}}


@pytest.mark.parametrize('failure', [
    'missing_transcript', 'unsupported_os', 'wrong_runtime_size',
    'missing_profile', 'duplicate_runtime', 'unbound_summary',
])
def test_runtime_evidence_failure_preserves_previously_published_version(tmp_path, failure):
    apk = tmp_path / 'synthetic.apk'
    root = tmp_path / 'releases'
    apk.write_bytes(b'previous synthetic publication')
    previous = publish(root, apk, publication_report(apk, 34),
                       expected_certificate=CERTIFICATE, now=100)
    apk.write_bytes(b'candidate synthetic publication')
    report = publication_report(apk, 35)
    change_evidence(report, failure)
    with pytest.raises(ReleaseUnavailable):
        publish(root, apk, report, expected_certificate=CERTIFICATE, now=200)
    assert ReleaseChannel(root).current(PACKAGE) == previous


@pytest.mark.parametrize('version', [1, 34, 35])
def test_lower_version_number_cannot_bypass_current_runtime_contract(tmp_path, version):
    apk = tmp_path / 'synthetic.apk'
    apk.write_bytes(b'not an executable APK')
    report = publication_report(apk, version)
    del report['installation_tests']
    with pytest.raises(ReleaseUnavailable):
        publish(tmp_path / 'releases', apk, report, expected_certificate=CERTIFICATE, now=100)


def test_archived_v3_version37_remains_readable_but_cannot_certify_version38(tmp_path):
    apk = tmp_path / "synthetic.apk"
    apk.write_bytes(b"synthetic historical artifact, never a real Android installation")
    root = tmp_path / "releases"
    report = publication_report(apk, 37)
    report["installation_tests"] = runtime_reports(report["sha256"], legacy=True)
    report["installation_evidence"] = from_ci_reports(report["installation_tests"], report["sha256"], version_code=37)
    previous = publish(root, apk, report, expected_certificate=CERTIFICATE, now=100)
    assert ReleaseChannel(root).current(PACKAGE) == previous
    assert ReleaseChannel(root).published(PACKAGE, previous.filename) == previous
    report["version_code"] = 38
    report["version_name"] = "0.13.0"
    with pytest.raises(ReleaseUnavailable):
        publish(root, apk, report, expected_certificate=CERTIFICATE, now=200)
    assert ReleaseChannel(root).current(PACKAGE) == previous


@pytest.mark.parametrize("version", [True, "37", 37.0, 0, -1, 2_100_000_001])
def test_invalid_version_cannot_select_a_historical_receipt_path(tmp_path, version):
    apk = tmp_path / "synthetic.apk"
    apk.write_bytes(b"synthetic receipt version guard")
    report = publication_report(apk, 37)
    report["installation_tests"] = runtime_reports(report["sha256"], legacy=True)
    report["installation_evidence"] = from_ci_reports(report["installation_tests"], report["sha256"], version_code=37)
    report["version_code"] = version
    with pytest.raises(ReleaseUnavailable):
        publish(tmp_path / "releases", apk, report, expected_certificate=CERTIFICATE, now=100)
