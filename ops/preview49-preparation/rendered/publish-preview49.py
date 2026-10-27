'Publish only the exact owner-authorized preview49; never attest a phone.'
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

APK_SHA = '9940c994d3e6695708fe65d64e378c6d998c8891ae69bbaa1c20df17008dbb6e'
APK_BYTES = 29937843
CERT = 'bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1'
OLD_SHA = '85fb8b3c3e0020080a421efaae1c101df0e55f97bacb791064e1b1cbaa4a8df1'
OLD_BYTES = 29937843
ARCHIVE_SHA = 'dc171704ffcf004aad7d8990408d301e9b3a63b6f030c0a5321e776cb7711fe4'
ARCHIVE_BYTES = 69716504
SOURCE_SHA = '8e4dc044ec6b700469a597cf8fc3a23aae96e57e5b5413e378dbf3986e2cef60'
SOURCE_BACKUP = '521d96293a048e4254bec936710bcfbf166b20a0'
BUILD_REPORT_SHA = '7af8b02af5070253d69b38734372f59d5f47e40961300122aca6e904a89459f0'
FOLDER = pathlib.Path('/var/lib/analyst-ai-build/incoming/windows-development-40453334023-1')
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
                (49, APK_SHA, PACKAGE, result['observed_at'])).fetchall()
        need(len(rows) <= 32, 'observation_too_many_versions')
        values = []
        for code, count, last_seen, exact_current in rows:
            need(all(type(value) is int for value in (code, count, last_seen, exact_current)),
                 'observation_noninteger_aggregate')
            need(0 <= code <= 2100000000 and 0 < count <= 1000000
                 and 0 <= last_seen <= result['observed_at'] and 0 <= exact_current <= count,
                 'observation_invalid_aggregate')
            values.append({'version_code': code, 'active_session_count': count,
                           'last_seen_at': last_seen, 'sessions_reporting_exact49': exact_current})
        result.update(status='read', versions=values,
                      exact49_reported_by_active_session=any(row['sessions_reporting_exact49'] > 0 for row in values))
    except (OSError, KeyError, sqlite3.Error, RuntimeError):
        # Phone observation is optional; never print SQL, session hashes, users, or exception text.
        result.update(status='unavailable', reason='readonly_observation_unavailable', versions=[])
    return result


need(os.geteuid() == 0, 'root_required')
# Bind this APK publication to the already deployed exact mandate sources.
required_runtime = {'autonomous_ai.py': {'bytes': 54368, 'sha256': '09d0f79dc25c6e0a21af0f4aad81845ac11333f5338bb899666535ef990d2e53'}, 'autonomous_controller.py': {'bytes': 36417, 'sha256': '1930c63e307d45b86a68fad0506a34b069a5fdf68cef99a6ed1e8d17588fb56e'}, 'background_dispatch.py': {'bytes': 9212, 'sha256': 'eefe68f2ff91f7be346fc8026ad4e15296bc197d73379e5c7158ed295e7add25'}, 'event_monitor.py': {'bytes': 8060, 'sha256': 'c5c853a1381369cfb0b95db922ec5d98536f261e727452970b2df6bdbc1378ad'}, 'market_schedule.py': {'bytes': 8958, 'sha256': '71fb3be626fb48856ec955a98a45b86023789e02060cd1bee79ab610c1abc1e1'}, 'volume_jobs.py': {'bytes': 19692, 'sha256': '4094b142b0f2b7522380e2d61bcb41a312493b5597bb1140f09a9a341ab5af06'}, 'volume_market.py': {'bytes': 33034, 'sha256': '5254e7eef732a28db8e3e3ed63b73a65b29ccdb983b78da686ce0bb3500ea87e'}, 'volume_monitor.py': {'bytes': 14454, 'sha256': 'ae8ca8ab1fbadc9271a37eee0c04807d1429097b96a00254ec943ae89b514b86'}, 'volume_workspace.py': {'bytes': 39906, 'sha256': '3c034e056e8af731d5d78cffda95f892f92a4ad5cb0c11b0774a6636953ce08d'}}
for directory in (pathlib.Path('/opt'), pathlib.Path('/opt/analyst-ai'), pathlib.Path('/opt/analyst-ai/backend')):
    trusted(directory, directory=True)
for name, item in required_runtime.items():
    need(file_sha(pathlib.Path('/opt/analyst-ai/backend') / name, item['bytes']) == item['sha256'], 'calendar_runtime_source_changed_before_publication')

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
need(build['github']['run_id'] == 40453334023 and build['github']['run_attempt'] == 1, 'wrong_build_run')
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
     and report['version_code'] == 49 and report.get('version_name') == '0.14.2-preview', 'wrong_apk_version')

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
    'Тестовая версия 0.14.2-preview. Расписание брокера управляет фоновым опросом цен; события, новости и выплаты проверяются отдельно. Возобновление прерванного сбора, приоритеты задач и защита сохранённых данных. Торговля выключена; нативная приёмка остаётся открытой.'
)
authorization = {'kind': 'owner_requested_latest_built_preview_delivery',
 'owner_request': 'Вся работа на ноуте; обновить рабочее приложение и APK на Timeweb без повторной полной '
                  'матрицы',
 'explicit_intermediate_preview': True,
 'date': '2026-10-27',
 'package_name': 'ru.omnicio.app.debug',
 'version_code': 49,
 'apk_sha256': '9940c994d3e6695708fe65d64e378c6d998c8891ae69bbaa1c20df17008dbb6e',
 'apk_bytes': 29937843,
 'certificate_sha256': 'bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1',
 'source_archive_sha256': 'dc171704ffcf004aad7d8990408d301e9b3a63b6f030c0a5321e776cb7711fe4',
 'source_archive_bytes': 69716504,
 'source_sha256': '8e4dc044ec6b700469a597cf8fc3a23aae96e57e5b5413e378dbf3986e2cef60',
 'source_backup_commit': '521d96293a048e4254bec936710bcfbf166b20a0',
 'build_report_sha256': '7af8b02af5070253d69b38734372f59d5f47e40961300122aca6e904a89459f0',
 'build_export_receipt_sha256': '0640ce9ae4333816b08e2f025d3b0dd678e8ac6abaa4ae2241cc9df9389f278e',
 'windows_run_id': 40453334023,
 'windows_run_attempt': 1,
 'full_check_and_build_passed': True,
 'preview_install_smoke': {'status': 'not_executed_for_published_build',
                           'run_id': None,
                           'full_runtime_matrix_passed': False,
                           'physical_phone_verified': False},
 'native_status': 'not_executed_for_published_build',
 'full15_runtime_matrix_passed': False,
 'complete_release_gate_passed': False,
 'runtime_pass': False,
 'phone_verified': False,
 'baseline_publication_sha256': '24cfc7637f14c922ac4d366feea9b1fd9dc50a99fd85dc822356aefc4b065cf2',
 'calendar_runtime_verification_sha256': '2920c8a03991d5c1792d64a10e05f92cea323f58791ab40732e1d6acbbf21782',
 'calendar_runtime_sources': {'autonomous_ai.py': {'bytes': 54368,
                                                   'sha256': '09d0f79dc25c6e0a21af0f4aad81845ac11333f5338bb899666535ef990d2e53'},
                              'autonomous_controller.py': {'bytes': 36417,
                                                           'sha256': '1930c63e307d45b86a68fad0506a34b069a5fdf68cef99a6ed1e8d17588fb56e'},
                              'background_dispatch.py': {'bytes': 9212,
                                                         'sha256': 'eefe68f2ff91f7be346fc8026ad4e15296bc197d73379e5c7158ed295e7add25'},
                              'event_monitor.py': {'bytes': 8060,
                                                   'sha256': 'c5c853a1381369cfb0b95db922ec5d98536f261e727452970b2df6bdbc1378ad'},
                              'market_schedule.py': {'bytes': 8958,
                                                     'sha256': '71fb3be626fb48856ec955a98a45b86023789e02060cd1bee79ab610c1abc1e1'},
                              'volume_jobs.py': {'bytes': 19692,
                                                 'sha256': '4094b142b0f2b7522380e2d61bcb41a312493b5597bb1140f09a9a341ab5af06'},
                              'volume_market.py': {'bytes': 33034,
                                                   'sha256': '5254e7eef732a28db8e3e3ed63b73a65b29ccdb983b78da686ce0bb3500ea87e'},
                              'volume_monitor.py': {'bytes': 14454,
                                                    'sha256': 'ae8ca8ab1fbadc9271a37eee0c04807d1429097b96a00254ec943ae89b514b86'},
                              'volume_workspace.py': {'bytes': 39906,
                                                      'sha256': '3c034e056e8af731d5d78cffda95f892f92a4ad5cb0c11b0774a6636953ce08d'}},
 'prior_native_attempt': {'run_id': 40389869187,
                          'build_run_id': 40386457173,
                          'status': 'failed',
                          'artifact_id': 12685050936,
                          'artifact_sha256': '9f8dc6419f23bcaf4fd964684582dcf7920fae9a0394aba44555cdd7c7869762',
                          'is_evidence_for_published_build': False},
 'reason_for_current_manifest_change': 'Owner requests an intermediate working update; exact build, '
                                       'signature, prior channel and deployed mandate are verified. '
                                       'Native/phone acceptance remains open.',
 'database_mutations_performed': False,
 'session_or_owner_binding_mutations_performed': False,
 'backend_deployment_performed': False,
 'service_restart_performed': False,
 'signing_key_mutations_performed': False,
 'trading_orders_submitted': False,
 'paid_ai_calls_performed': False}
candidate = AndroidRelease.parse({
    'schema_version': 1, 'package_name': PACKAGE, 'version_code': 49, 'version_name': '0.14.2-preview',
    'apk_sha256': APK_SHA, 'apk_bytes': APK_BYTES, 'certificate_sha256': CERT, 'min_sdk': 37,
    'published_at': int(time.time()), 'notes': notes,
})
channel = ReleaseChannel(ROOT)
with publication_lock(directory):
    old = channel.current(PACKAGE)
    need(old.certificate_sha256 == CERT, 'previous_certificate_changed')
    previous_is_exact48 = (old.version_code == 48 and old.version_name == '0.14.1-preview'
                           and old.apk_sha256 == OLD_SHA and old.apk_bytes == OLD_BYTES)
    current_is_exact49 = (old.version_code == 49 and old.version_name == '0.14.2-preview'
                          and old.apk_sha256 == APK_SHA and old.apk_bytes == APK_BYTES)
    need(previous_is_exact48 or current_is_exact49, 'unexpected_current_release')
    previous_path = FOLDER / 'before-owner-preview49-current.json'
    if previous_is_exact48:
        save_new(previous_path, bounded_file(directory / 'current.json', 16384))
    else:
        previous = AndroidRelease.parse(json.loads(bounded_file(previous_path, 16384)))
        need(previous.version_code == 48 and previous.apk_sha256 == OLD_SHA
             and previous.apk_bytes == OLD_BYTES and previous.certificate_sha256 == CERT,
             'retry_previous_release_receipt_conflict')
    save_new(FOLDER / 'owner-preview49-authorization.json', encoded(authorization))
    existing = _existing_current(channel, directory, candidate)
    if existing is not None:
        candidate = existing
    else:
        candidate = _resume_prepared(channel, directory, candidate)
        with tempfile.TemporaryDirectory(prefix='owner-preview49-', dir=FOLDER) as scratch:
            apk = pathlib.Path(scratch) / 'candidate.apk'
            save_new(apk, apk_data)
            _stage_candidate(channel, directory, candidate, apk)
    trusted(directory / 'current.json', public=True)
    trusted(directory / candidate.filename, public=True)
    current = channel.current(PACKAGE)
    need(current == candidate and current.version_code == 49 and current.apk_sha256 == APK_SHA,
         'channel_activation_failed')
    need(file_sha(channel.verified_file(current), APK_BYTES) == APK_SHA, 'published_bytes_changed')
    receipt = {**authorization, 'version_name': current.version_name, 'published_at': current.published_at,
               'url': PUBLIC_ORIGIN + '/client/apk/' + current.filename,
               'channel_version': 49, 'previous_version': 48, 'previous_apk_sha256': OLD_SHA,
               'publication_method': 'existing_locked_atomic_immutable_release_api'}
    save_new(FOLDER / 'owner-preview49-delivery.json', encoded(receipt))
print('OWNER_PREVIEW49_DELIVERY=' + json.dumps(receipt, ensure_ascii=True), flush=True)
print('OWNER_PREVIEW49_CLIENT_OBSERVATIONS=' + json.dumps(observed_clients(), ensure_ascii=True), flush=True)
