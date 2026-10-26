'Publish only the exact owner-authorized preview44; never attest a phone.'
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
import pathlib
import pwd
import sqlite3
import stat
import sys
import tempfile
import time
import zipfile

APK_SHA = 'f0af0b45515143f8abb2c28e73d0d484acde5c6a36e18de1b398692bc45a4cf6'
APK_BYTES = 29771254
CERT = 'bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1'
OLD_SHA = '4e9bf0a2fd54d8ab4b9d49ef9ddf96bc14a274ac4c145585fcfdb88d6ae774b6'
OLD_BYTES = 29771254
ARCHIVE_SHA = 'f8dd107e1714fcc1a3aeed4afd25b6d9efa3dca878b7106191f3fd77e4fa1b89'
ARCHIVE_BYTES = 68927139
SOURCE_SHA = 'e34b717fa408fbe377d910a372933c35a2ba1bdddf02263b6daa477df70f93b9'
SOURCE_BACKUP = '1cc05586b6874bfdd0cdb80131d178de9f95870c'
BUILD_REPORT_SHA = '808a43afb0585b3cf2cd9519d54c525f51be4d66fa239e3d9c4c4257d2eafd40'
FOLDER = pathlib.Path('/var/lib/analyst-ai-build/incoming/windows-development-40282775349-1')
ROOT = pathlib.Path('/srv/analyst-ai-ota/releases')
PACKAGE = 'ru.omnicio.app.debug'
PUBLIC_ORIGIN = 'https://analyst-ai-2941515.twc1.net'


def need(value, message):
    if not value:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def trusted(path, *, directory=False, public=False):
    info = path.lstat()
    need((stat.S_ISDIR if directory else stat.S_ISREG)(info.st_mode), 'unexpected_path_type')
    need(info.st_uid == 0 and not info.st_mode & 0o022 and path.resolve(strict=True) == path,
         'untrusted_path')
    if not directory:
        need(info.st_nlink == 1, 'hardlinked_file')
    if public:
        need(info.st_mode & (0o001 if directory else 0o004), 'not_publicly_readable')
    return info


def bounded_file(path, limit):
    need(trusted(path).st_size <= limit, 'file_size_limit')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        raw = stream.read(limit + 1)
    need(len(raw) <= limit, 'file_size_changed')
    return raw


def file_sha(path, expected_size):
    need(trusted(path).st_size == expected_size, 'file_size_mismatch')
    digest = hashlib.sha256()
    total = 0
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        for block in iter(lambda: stream.read(min(1024**2, expected_size - total + 1)), b''):
            total += len(block)
            need(total <= expected_size, 'file_grew_during_read')
            digest.update(block)
    need(total == expected_size, 'file_truncated_during_read')
    return digest.hexdigest()


def save_new(path, data):
    if path.exists() or path.is_symlink():
        need(bounded_file(path, len(data)) == data, 'existing_receipt_conflict')
        return
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def observed_clients():
    """Read session aggregates only; never fabricate readiness or modify SQLite."""
    result = {
        'scope': 'active_authenticated_preview_sessions',
        'client_headers_are_not_device_attestation': True,
        'physical_phone_verified': False,
        'database_open_mode': 'ro',
        'query_only': True,
        'observed_at': int(time.time()),
    }
    path = pathlib.Path('/var/lib/analyst-ai/backend.db')
    try:
        owner = pwd.getpwnam('analyst-ai').pw_uid
        folder_info = path.parent.lstat()
        info = path.lstat()
        need(path.resolve(strict=True) == path and path.parent.resolve(strict=True) == path.parent,
             'observation_path_alias')
        need(stat.S_ISDIR(folder_info.st_mode) and folder_info.st_uid in (0, owner)
             and not folder_info.st_mode & 0o022, 'observation_directory_untrusted')
        need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid in (0, owner)
             and not info.st_mode & 0o022, 'observation_database_untrusted')
        # mode=ro sees the live WAL. immutable=1 would risk a stale observation.
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro&cache=private', uri=True, timeout=1)) as db:
            db.execute('PRAGMA query_only=ON')
            need(db.execute('PRAGMA query_only').fetchone() == (1,), 'observation_query_only_missing')
            deadline = time.monotonic() + 2
            db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            rows = db.execute('''SELECT c.version_code, COUNT(*), MAX(c.observed_at),
                SUM(CASE WHEN c.version_code=? AND c.release_sha256=? THEN 1 ELSE 0 END)
                FROM client_versions c JOIN sessions s
                ON s.token_hash=c.session_hash AND s.user_id=c.user_id
                WHERE c.package_name=? AND s.expires_at>?
                GROUP BY c.version_code ORDER BY c.version_code DESC LIMIT 33''',
                (44, APK_SHA, PACKAGE, result['observed_at'])).fetchall()
        need(len(rows) <= 32, 'observation_too_many_versions')
        values = []
        for code, count, last_seen, exact_current in rows:
            need(all(type(value) is int for value in (code, count, last_seen, exact_current)),
                 'observation_noninteger_aggregate')
            need(0 <= code <= 2100000000 and 0 < count <= 1000000
                 and 0 <= last_seen <= result['observed_at'] and 0 <= exact_current <= count,
                 'observation_invalid_aggregate')
            values.append({'version_code': code, 'active_session_count': count,
                           'last_seen_at': last_seen, 'sessions_reporting_exact44': exact_current})
        result.update(status='read', versions=values,
                      exact44_reported_by_active_session=any(row['sessions_reporting_exact44'] > 0 for row in values))
    except (OSError, KeyError, sqlite3.Error, RuntimeError):
        # Phone observation is optional; never print SQL, session hashes, users, or exception text.
        result.update(status='unavailable', reason='readonly_observation_unavailable', versions=[])
    return result


need(os.geteuid() == 0, 'root_required')
for path in (pathlib.Path('/var'), pathlib.Path('/var/lib'), FOLDER.parent, FOLDER):
    trusted(path, directory=True)
# The established build workspace belongs to analyst-build; its incoming
# subdirectory and exact archive folder were created root-owned by collect.
build_root = FOLDER.parent.parent
build_info = build_root.lstat()
need(stat.S_ISDIR(build_info.st_mode) and build_root.resolve(strict=True) == build_root
     and build_info.st_uid in (0, pwd.getpwnam('analyst-build').pw_uid)
     and not build_info.st_mode & 0o022, 'untrusted_build_workspace')
archive = FOLDER / 'windows-development-evidence.zip'
need(file_sha(archive, ARCHIVE_BYTES) == ARCHIVE_SHA, 'wrong_evidence_archive')
apk_member = 'outputs/app/build/outputs/apk/preview/app-preview.apk'
report_member = 'outputs/app/build/outputs/apk/preview/apk-verification.json'
build_member = 'evidence/windows-development.json'
with zipfile.ZipFile(archive) as bundle:
    names = bundle.namelist()
    need(len(names) == len(set(names)), 'duplicate_archive_member')
    need(bundle.getinfo('windows-development-envelope.json').file_size < 4 * 1024**2, 'envelope_too_large')
    envelope = json.loads(bundle.read('windows-development-envelope.json'))
    need(envelope['schema'] == 1 and envelope['kind'] == 'windows_check_build_source_archive', 'wrong_archive_kind')
    need(envelope['source_sha256'] == SOURCE_SHA, 'wrong_source_identity')
    need(envelope['runtime_pass'] is False and envelope['phone_verified'] is False
         and envelope['publication_authorized'] is False, 'unexpected_archive_claim')
    controller = envelope['controller']
    need(controller.get('worker_started') is True and controller.get('worker_exit_code') == 0
         and controller.get('owned_processes_after') == 0 and not controller.get('error')
         and not controller.get('cleanup_error'), 'build_worker_cleanup_not_passed')
    members = {}
    for name, limit in ((apk_member, APK_BYTES), (report_member, 4 * 1024**2), (build_member, 4 * 1024**2)):
        need(bundle.getinfo(name).file_size <= limit, 'archive_member_too_large')
        raw = bundle.read(name)
        expected = envelope['files'][name]
        need(expected['bytes'] == len(raw) and expected['sha256'] == sha(raw), 'export_member_changed')
        members[name] = raw
apk_data = members[apk_member]
need(len(apk_data) == APK_BYTES and sha(apk_data) == APK_SHA, 'wrong_apk_bytes')
need(sha(members[build_member]) == BUILD_REPORT_SHA, 'wrong_verified_build_report')
build = json.loads(members[build_member])
need(build == envelope['report'], 'envelope_report_conflict')
need(build['github']['run_id'] == 40282775349 and build['github']['run_attempt'] == 1, 'wrong_build_run')
need(build['status'] == 'passed_check_and_build_only' and build['check']['status'] == 'passed'
     and build['build']['status'] == 'passed', 'full_build_not_passed')
need(all(build[key] == SOURCE_SHA for key in ('source_sha256', 'source_sha256_after'))
     and build['check']['source_sha256'] == SOURCE_SHA and build['build']['source_sha256'] == SOURCE_SHA,
     'build_source_identity_changed')
need(build['build']['apk_sha256'] == APK_SHA and build['certificate_sha256'] == CERT
     and build['apks']['app/build/outputs/apk/preview/app-preview.apk'] == {'sha256': APK_SHA, 'bytes': APK_BYTES},
     'build_apk_identity_conflict')
report = json.loads(members[report_member])
need(report.get('package') == PACKAGE and type(report.get('version_code')) is int
     and report['version_code'] == 44 and report.get('version_name') == '0.13.6-preview', 'wrong_apk_version')

for path in (pathlib.Path('/opt'), pathlib.Path('/opt/analyst-ai'), pathlib.Path('/opt/analyst-ai/backend')):
    trusted(path, directory=True)
for name in ('client_updates.py', 'client_compatibility.py', 'release_publication.py', 'release_lock.py',
             'release_json.py', 'release_bytes.py', 'installation_evidence.py'):
    trusted(pathlib.Path('/opt/analyst-ai/backend') / name)
sys.path.insert(0, '/opt/analyst-ai')
from backend.client_updates import AndroidRelease, ReleaseChannel
from backend.release_lock import publication_lock
from backend.release_publication import _require_apk_evidence, _require_android_floor, _existing_current, _resume_prepared, _stage_candidate

_require_apk_evidence(report, sha256=APK_SHA, size=APK_BYTES, certificate=CERT)
_require_android_floor(report)
directory = ROOT / PACKAGE
for path in (pathlib.Path('/srv'), ROOT.parent, ROOT, directory):
    trusted(path, directory=True, public=True)
trusted(directory / 'current.json', public=True)
notes = (
    'Тестовая версия 0.13.6-preview. Список сохранённых исследований и открытый материал теперь сохраняют положения прокрутки отдельно. Полная проверка интерфейса продолжается.'
)
authorization = {'kind': 'owner_requested_latest_built_preview_delivery',
 'owner_request': 'Не забывай обновлять приложение! Постоянно если есть актуальная сборка апк то обнови ту '
                  'что на телефоне!',
 'date': '2026-10-26',
 'package_name': 'ru.omnicio.app.debug',
 'version_code': 44,
 'apk_sha256': 'f0af0b45515143f8abb2c28e73d0d484acde5c6a36e18de1b398692bc45a4cf6',
 'apk_bytes': 29771254,
 'certificate_sha256': 'bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1',
 'source_archive_sha256': 'f8dd107e1714fcc1a3aeed4afd25b6d9efa3dca878b7106191f3fd77e4fa1b89',
 'source_archive_bytes': 68927139,
 'source_sha256': 'e34b717fa408fbe377d910a372933c35a2ba1bdddf02263b6daa477df70f93b9',
 'source_backup_commit': '1cc05586b6874bfdd0cdb80131d178de9f95870c',
 'build_report_sha256': '808a43afb0585b3cf2cd9519d54c525f51be4d66fa239e3d9c4c4257d2eafd40',
 'build_export_receipt_sha256': 'aea3b2586adf4f62304bb66495e154c0c015b45ebbaed7dca6f04157f7ef6c43',
 'windows_run_id': 40282775349,
 'windows_run_attempt': 1,
 'full_check_and_build_passed': True,
 'preview_install_smoke': {'run_id': 40287655859,
                           'run_attempt': 1,
                           'artifact_id': 12634694629,
                           'artifact_sha256': '16e4e8c9bd3f28d8e4faa6f8a36933674f19d68b6f7c264c116350fde8ba1202',
                           'artifact_bytes': 4502633,
                           'installation_json_sha256': '498ba1d2ca64fd2ffd0c6baaa9eb665f8a4309f79cdeabc08d353f90b09e428a',
                           'build_provenance_sha256': 'c33f30b25bd455e275a783f4c0183925011221d3f78574addd9807b7dc90f43a',
                           'summary_sha256': 'd25b495152ca8aae09b622a2372ea95cd401134bf2641a26a84a306c68bef635',
                           'envelope_sha256': '77986fb788fec278b5b061674c850fda7410afa9550b5196c9d0135f59bc30a3',
                           'runtime_sha256': '3565db7329b6b0eb199b22bc7fe98a0ddb41b1714d64f849627aa9923d0adfc1',
                           'runtime_exit_code': 1,
                           'original14_status': 'incomplete',
                           'original14': {'complete': False, 'required_cases': 14, 'observed_cases': 0},
                           'evidence_verified_at_workflow_preparation': True,
                           'android_api': 37,
                           'abi': 'x86_64',
                           'page_size_bytes': 16384,
                           'previous43_clean_install': True,
                           'upgrade43_to44': True,
                           'upgrade44_bootstrap_launch': True,
                           'candidate44_clean_install': True,
                           'candidate44_bootstrap_launch': True,
                           'physical_phone_verified': False,
                           'full_runtime_matrix_passed': False},
 'original14_run_id': 40287655859,
 'original14_status': 'incomplete',
 'full15_runtime_matrix_passed': False,
 'complete_release_gate_passed': False,
 'runtime_pass': False,
 'phone_verified': False,
 'reason_for_current_manifest_change': 'Publish the exact latest built preview under the existing mandatory '
                                       'client update channel, as directly requested by the owner.',
 'database_mutations_performed': False,
 'session_or_owner_binding_mutations_performed': False,
 'backend_deployment_performed': False,
 'service_restart_performed': False,
 'signing_key_mutations_performed': False,
 'trading_orders_submitted': False,
 'paid_ai_calls_performed': False}
candidate = AndroidRelease.parse({
    'schema_version': 1, 'package_name': PACKAGE, 'version_code': 44, 'version_name': '0.13.6-preview',
    'apk_sha256': APK_SHA, 'apk_bytes': APK_BYTES, 'certificate_sha256': CERT, 'min_sdk': 37,
    'published_at': int(time.time()), 'notes': notes,
})
channel = ReleaseChannel(ROOT)
with publication_lock(directory):
    old = channel.current(PACKAGE)
    need(old.certificate_sha256 == CERT, 'previous_certificate_changed')
    previous_is_exact43 = (old.version_code == 43 and old.version_name == '0.13.5-preview'
                           and old.apk_sha256 == OLD_SHA and old.apk_bytes == OLD_BYTES)
    current_is_exact44 = (old.version_code == 44 and old.version_name == '0.13.6-preview'
                          and old.apk_sha256 == APK_SHA and old.apk_bytes == APK_BYTES)
    need(previous_is_exact43 or current_is_exact44, 'unexpected_current_release')
    previous_path = FOLDER / 'before-owner-preview44-current.json'
    if previous_is_exact43:
        save_new(previous_path, bounded_file(directory / 'current.json', 16384))
    else:
        previous = AndroidRelease.parse(json.loads(bounded_file(previous_path, 16384)))
        need(previous.version_code == 43 and previous.apk_sha256 == OLD_SHA
             and previous.apk_bytes == OLD_BYTES and previous.certificate_sha256 == CERT,
             'retry_previous_release_receipt_conflict')
    save_new(FOLDER / 'owner-preview44-authorization.json', encoded(authorization))
    existing = _existing_current(channel, directory, candidate)
    if existing is not None:
        candidate = existing
    else:
        candidate = _resume_prepared(channel, directory, candidate)
        with tempfile.TemporaryDirectory(prefix='owner-preview44-', dir=FOLDER) as scratch:
            apk = pathlib.Path(scratch) / 'candidate.apk'
            save_new(apk, apk_data)
            _stage_candidate(channel, directory, candidate, apk)
    trusted(directory / 'current.json', public=True)
    trusted(directory / candidate.filename, public=True)
    current = channel.current(PACKAGE)
    need(current == candidate and current.version_code == 44 and current.apk_sha256 == APK_SHA,
         'channel_activation_failed')
    need(file_sha(channel.verified_file(current), APK_BYTES) == APK_SHA, 'published_bytes_changed')
    receipt = {**authorization, 'version_name': current.version_name, 'published_at': current.published_at,
               'url': PUBLIC_ORIGIN + '/client/apk/' + current.filename,
               'channel_version': 44, 'previous_version': 43, 'previous_apk_sha256': OLD_SHA,
               'publication_method': 'existing_locked_atomic_immutable_release_api'}
    save_new(FOLDER / 'owner-preview44-delivery.json', encoded(receipt))
print('OWNER_PREVIEW44_DELIVERY=' + json.dumps(receipt, ensure_ascii=True), flush=True)
print('OWNER_PREVIEW44_CLIENT_OBSERVATIONS=' + json.dumps(observed_clients(), ensure_ascii=True), flush=True)
