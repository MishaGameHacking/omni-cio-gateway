"""Install eight reviewed decision-engine modules; retain the compatible password baseline."""
from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timezone
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import stat
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
import zipfile

BASE = 'a9574656fcac4507660c872ebcc22641154a3c8a'
WHEEL_SHA = 'c8ca4d9a360dbd5d4b9bb7a8389e2a9ae6a106bee722b496f918040ba2daa17e'
MODULES = frozenset({'autonomous_controller.py', 'decision_cycle.py', 'decision_views.py',
                     'strategy_actions.py', 'purchase_policy.py', 'volume_live.py', 'margin_policy.py',
                     'volume_chat.py'})
# Immutable Git blob identities of the deployed a957 backend (105 files).
BASELINE_BLOBS = {'ai_broker_access.py': 'b182ad2310f39a518ff329c91ed4fa81a465d1a1',
 'ai_budget.py': '36ae45ae5d7b33c55b3dee614c9ead9ea41f575a',
 'ai_guarded_client.py': 'd274eb0dd00e9c7d0c0bd7cf8a48d6bef4f73a6d',
 'ai_jobs.py': '9369978cffdc79c3498727676786657ca4f091e1',
 'ai_policy.py': '4940ab8c903a55cf74e07fe93499dd2745e95e87',
 'ai_route_catalog.py': '4da2c6d3f8f808a44df1201448b5451772847181',
 'allocation_plan.py': '08f8741031ec28b44271d0c8f247602fd9a5ec73',
 'analysis_engine.py': '3552f85ff993e4eba231fe3536f60e476fc32109',
 'android_runtime_contract.py': '2bece677b34096d526363d0ec4644ae7c2eaf784',
 'app.py': 'a68eef110e6efbfb521316ec84244b46801c997a',
 'application_hierarchy.py': 'b8f34906b5799b1ae3eb17a8b2f06ce0ba2e9c16',
 'automation_ui_evidence.py': '29e11a710baa7a116a5fe5b9163c8d45e9e54c6e',
 'autonomous_ai.py': '7d3796b749953f339fe605f4c73660d62c8851a2',
 'autonomous_controller.py': 'fe29e220af2a3205d5bca71e2d070f38445955ee',
 'background_dispatch.py': '260a231db15d27c37c577e12d4b6170e26bdffe3',
 'bounded_ai_response.py': 'f4c7c4dd79fe49f9ed0d9549750a5d1ddb9ce619',
 'broker_connections.py': 'fd7367f0c4e8a6fccca9c73f22fa9c31c16ed361',
 'client_compatibility.py': '85d75d67a51e386d8eb15356b36a1cb16ccef646',
 'client_diagnostics.py': 'c9c674923c58abefcdc81b70c34fdb03ee7ce752',
 'client_updates.py': '5c89c98f122944d50117b527551f0f649693dfac',
 'credit_evidence.py': '26a58c95dfec7827c1d7abac956da9dbf4069916',
 'decision_views.py': '2bad000e72175c99702ba7ea0b44f2579fe26dbd',
 'event_monitor.py': '10c41c8453a56c2474612fa3d99ec0643de8c7ec',
 'evidence_history.py': '1d0ca9492d2f44937b320db94585baf8696c7e62',
 'evidence_order.py': '5e6dcc8d08ce021e7634c5d8235c0f8e63d17adc',
 'evidence_revision.py': '0546a469986c6e2a0ac18a9335ec177e6d54166f',
 'fund_policy.py': 'ce74b404ae1d48d484f2030ee1c4a3059fe982cc',
 'installation_evidence.py': '9ed34abec5eada18aabd1f9a7d72d4d2ae32dfeb',
 'investment_chat_policy.py': '9452c47b4556a2feecf7fdbdd9c8df32522bbfcd',
 'investment_links.py': '8d4787e92222ded57aef85d9754749bee270b83d',
 'market_schedule.py': 'f72f8660fc75429b96f7d47ad8f14b218961a4da',
 'model_json_limits.py': '8ca718100438d87b7eda02bb04af25a1b7f42c5e',
 'monitoring_access.py': '6e098617d9c14eab067c9e1b46c0ef2f0dcad49f',
 'operations_ledger.py': '8e93b7b52e39360b11631e5fca73ec2440a3270e',
 'osint_analysis.py': 'e5f8a3edd7985d4980d5cfd9cce7beadbad7d034',
 'osint_api.py': '118dfe55a7a06f916255bae2978840fd6da3c057',
 'osint_catalogue.py': '55ac056a9adf7ec80155742348899b7a3f15a1a4',
 'osint_content.py': '2064569884391adb2000f79401c91875f3e46ad3',
 'osint_network.py': '1d51fd70d5dab4de17c0e6fdab02889d8cd8ee8f',
 'osint_pdf.py': '5e9792e9f4c1da9c8f13695cf2fc4fcae038765f',
 'osint_read.py': '2c694d0a3ba391e10022314ca4f4196738e5f54a',
 'osint_retention.py': '7dd03ab7e8b1e75905fd149fdb7de5c0265a4843',
 'osint_store.py': 'a18e63f7a0dbd8d5b1622100a63b2f3ab407040e',
 'osint_worker.py': '560a1c37325741852d8d8a2576e3b96bc5892532',
 'owner_access.py': '4062f1ebfc86a31e3152d143db5bd9ccf2dbc52e',
 'owner_app.py': 'eea3a5e8ddeccd08fa8bb960e15b1a1f4e2d04e6',
 'owner_password.py': '69314e8501e26db9ab02cc5b1d4b268a39d2a11d',
 'owner_password_routes.py': '53bc9984fbd5cc52c3fb729ce8e5d0fe271b2501',
 'paper_execution.py': 'e40cda179dcbc66cce157d93ceccf600202d090b',
 'portfolio_accounting.py': '6db02da95cf24119042175c4ff849665cfdeaf2e',
 'portfolio_details.py': '78e1c2123f7921795c02bcb14ef615eed9476c81',
 'portfolio_mandate.py': 'b92ff53e83dae171da7887256c8c19435110339d',
 'portfolio_research.py': '7ca34284f1569f6df4f946740b6d0aeda83f6e7a',
 'portfolio_risk.py': 'd5a72e23e4c53d287877a4301c0a2035b37602b2',
 'portfolio_scenarios.py': '0d887e38ed07d968294342852cd05dad70f01590',
 'public_sources.py': '486d7f27d395780b05abd49ff42560425fcc5719',
 'public_updates_app.py': '1bbca2b2e59501517d37331b2a475d9195d898c3',
 'purchase_policy.py': 'e60f82e4095c73d4723f7ef9b9e977c76b3ccc2f',
 'release_bytes.py': '608bd9fd410736d24f45b46c622b0632f0fc0ebd',
 'release_contract.py': '3ba25146f780d1cc0eee86465e7cf6c73b32af14',
 'release_json.py': '787697b5b86b6b698ba9757440f9fe3b31a0c932',
 'release_lock.py': '3859f3e4c5397c44e44b0dbd1e320c8957360142',
 'release_publication.py': '48bf41cddf2926617683b9d40a7f29c35c43ca99',
 'requirements.txt': 'd420bbaf69f3c79f0b4959ed1dd014a4aaffaa7d',
 'research_clock.py': '36ec6b0a8ff0f7cfa44a4d11795b592e22cb2e79',
 'research_import.py': '224f9aed83859f8a963f96b7a51a7582e750aa8a',
 'research_profile_cache.py': 'a2050a709ec8588618f73472beaebeea5ee48608',
 'research_snapshot.py': '97ce21b8ca82662bbd6866d1f458eb1259c8065d',
 'research_store.py': '9e6473ed3ec97c39bede49a20f26f3ad7cc1edb9',
 'risk_math.py': '15528c208b96c7aa5fa3ca1bde3aebc1e95fe1b4',
 'risk_preview.py': 'd3743b5a51adeed6eb29b86b6be5bcbb6014e793',
 'schema_migrations.py': '2c7f03cebc3f3ddb92c34a56249611bf3abaca0a',
 'server_version.py': '54f0c33521ef77153b8809450be2039ddb9e0dd6',
 'source_observability.py': 'c174a21b71c81ddc5cd3e829b0b16e32d1a8ed99',
 'strategy_actions.py': '632c186cd1e0a797264d9cd99474d310d1f00fbd',
 'strategy_activity.py': 'd8d102900149db2edb0b5309c242c7d31941877a',
 'strategy_construction.py': 'fd88ca5173a5be2e6555f0bec49d16b9d0342a8d',
 'strategy_profiles.py': '6f2f3f5d8f7ef6ed495d7c175c165e1bd8047156',
 'strategy_sales.py': 'e1de62854972c8bb556554c7e438c9e0ce2dfc07',
 'strategy_yield.py': 'dc0f0464b6f651b915c0a1b54f6bea84726d1136',
 'telegram_browser_app.py': '04f0def718aeadd1dc3a96e09abc4ebd3964b31b',
 'telegram_oidc.py': '3e9c735dbf8b3dca7fa18626a05e480b67125f9f',
 'timeweb_ai.py': '4378b4dfa8d3bd9a30b6c838b3480f7a1bb0b34c',
 'tinvest_portfolio.py': 'ab2eb927df7e38806f64518fcf13962a30c04b22',
 'volume.py': 'd2eba4cb88620ef1069cbc1f2b0eaeffb4d1ba20',
 'volume_analysis.py': 'ca9545390ab3f5abcdcfb7f6c058476d12a8fed0',
 'volume_catalogue.py': 'eb7b2d9bb8b7e458b206e30866cdf1d93d1bbb65',
 'volume_chat.py': '7655dbc0164a71425a2e0f9b50aeeb22818e3a7e',
 'volume_contract.py': 'f31abae3e42896fab46b25a9bdfc5f702e64d7ae',
 'volume_credit.py': '4c9c23ea0bc8d192eae39744f9c6d51de0e4a952',
 'volume_devices.py': '187d82bc3e970883662521ab7119a7accba1fa5e',
 'volume_explanations.py': 'ea75cd04d96ee791aa6f3d7bb6db04d9513b404a',
 'volume_impact.py': '34545497358d8718e9e2860b4d070293e48285bb',
 'volume_jobs.py': '1892299fd4c2d911b4ba430da44a8f0d3bb1b0bf',
 'volume_live.py': '0072033a9cccd28361dcd0e5629c6570d4c214cc',
 'volume_market.py': '0fe5e5930fe66c1ac2fc36353c1ba05f274a6d3c',
 'volume_monitor.py': '63574cc38115c8447468c000ade6142f9dc77108',
 'volume_news.py': '857aef1d19bb20a25edf543bde5c85ad9f72c5bf',
 'volume_notifications.py': '32ba592be696c31219b46ad935ebc5d05c84c37d',
 'volume_plans.py': 'eada38c394aea69758b54f26565cfae5f5649dd0',
 'volume_presentation.py': '6dc0466fd685908bd338e1c95f9e54338cd38438',
 'volume_purchases.py': '51a8e7a69a5743d48dd9b1b54151f206300e81b7',
 'volume_state.py': '14c6931a4b4ea9e9c865fca5decca4ceb13d11e4',
 'volume_workspace.py': 'baeab2ad04dc6b08d24e05efd115d511de17c920',
 'workspace_readiness.py': '1c35534a9ad9711dac0cf564b848aa49787e684b'}

SERVICES = ('analyst-ai-owner.service', 'analyst-ai-updates.service')
PUBLIC = 'https://analyst-ai-2941515.twc1.net'
CONFIGURATION = Path('/etc/analyst-ai/backend.env')


class RollbackBlocked(RuntimeError):
    """Retain candidate code when source rollback cannot be proven safe."""


class CompatibleRollbackBlocked(RollbackBlocked):
    """Recovery cannot be proven to preserve the deployed password baseline."""


class ServiceRollbackBlocked(RollbackBlocked):
    """Do not change code while an owner process could still enroll credentials."""


def need(condition, code):
    if not condition:
        raise RuntimeError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def validate(bundle):
    need(bundle['schema'] == 1 and bundle['base_commit'] == BASE
         and bundle['host'] == 'LAPTOP-NPSGA016' and bundle['apk_changed'] is False,
         'unexpected_release_contract')
    need(re.fullmatch('[a-f0-9]{40}', bundle['source_commit']), 'invalid_source_commit')
    need(bundle.get('run_attempt') == '1' and re.fullmatch('[0-9]{8,20}', str(bundle.get('run_id', ''))),
         'unverified_run_identity')
    need(set(bundle['files']) == MODULES, 'unreviewed_module_set')
    expected = bundle['expected']
    need(set(expected) == set(BASELINE_BLOBS), 'incomplete_runtime_baseline')
    for name, value in expected.items():
        need(re.fullmatch('[a-z_][a-z0-9_]*\\.py|requirements\\.txt', name)
             and re.fullmatch('[a-f0-9]{64}', value), 'invalid_baseline_identity')
    for name, row in bundle['files'].items():
        data = row['content'].encode('utf-8')
        need(0 < len(data) <= 512 * 1024 and row['before'] == expected.get(name)
             and digest(data) == row['after'], 'invalid_module_identity')


def dependency_entries(dependency):
    need(dependency['name'] == 'pypdf-6.21.3-py3-none-any.whl'
         and dependency['version'] == '6.21.3' and dependency['sha256'] == WHEEL_SHA,
         'unreviewed_pdf_dependency')
    raw = base64.b64decode(dependency['content_base64'], validate=True)
    need(len(raw) <= 1024 * 1024 and digest(raw) == WHEEL_SHA, 'pdf_dependency_digest_changed')
    with zipfile.ZipFile(io.BytesIO(raw)) as wheel:
        entries = wheel.infolist()
        need(len(entries) <= 300 and sum(item.file_size for item in entries) <= 8 * 1024**2,
             'pdf_dependency_size_invalid')
        result = {}
        for item in entries:
            path = PurePosixPath(item.filename)
            need(not path.is_absolute() and '..' not in path.parts and '\\' not in item.filename
                 and path.parts[0] in {'pypdf', 'pypdf-6.21.3.dist-info'}
                 and not stat.S_ISLNK(item.external_attr >> 16), 'pdf_dependency_path_invalid')
            if not item.is_dir():
                need(item.filename not in result, 'pdf_dependency_duplicate_path')
                result[item.filename] = wheel.read(item)
    need('pypdf/__init__.py' in result and 'pypdf-6.21.3.dist-info/METADATA' in result,
         'pdf_dependency_incomplete')
    return result


def install_dependency(root, entries):
    destination = root / '_osint_vendor'
    need(not destination.exists() and not destination.is_symlink(), 'pdf_dependency_already_present')
    destination.mkdir(mode=0o755)
    metadata = (root / 'app.py').stat()
    try:
        for relative, raw in entries.items():
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as output:
                output.write(raw)
            path.chmod(0o644)
            need(path.read_bytes() == raw, 'pdf_dependency_installed_bytes_changed')
        if hasattr(os, 'chown'):
            for path in [destination, *destination.rglob('*')]:
                os.chown(path, metadata.st_uid, metadata.st_gid)
                if path.is_dir():
                    path.chmod(0o755)
    except BaseException:
        shutil.rmtree(destination)
        raise
    return destination


def verify_dependency(root, entries):
    vendor = root / '_osint_vendor'
    need(vendor.is_dir() and not vendor.is_symlink(), 'pdf_dependency_missing')
    for relative, expected in entries.items():
        need(read_regular(vendor / relative) == expected, 'pdf_dependency_installed_bytes_changed')


def read_regular(path):
    need(path.is_file() and not path.is_symlink() and path.resolve(strict=True) == path
         and path.stat().st_nlink == 1, 'unsafe_runtime_file')
    return path.read_bytes()


def git_blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def verify_base(root, expected, changes):
    need(root.is_dir() and root.resolve(strict=True) == root, 'unsafe_runtime_directory')
    for name, value in expected.items():
        raw = read_regular(root / name)
        need(digest(raw) == value and git_blob(raw) == BASELINE_BLOBS[name],
             'runtime_changed_since_baseline')
    for name, row in changes.items():
        if row['before'] is None:
            need(not (root / name).exists() and not (root / name).is_symlink(),
                 'new_module_already_exists')


def verify_unchanged_modules(root, expected):
    for name, value in expected.items():
        if name not in MODULES:
            raw = read_regular(root / name)
            need(digest(raw) == value and git_blob(raw) == BASELINE_BLOBS[name],
                 'compatible_baseline_changed')


def replace_file(path, raw, template):
    metadata = template.stat()
    temporary = path.with_name(path.name + '.server-release-new')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        if hasattr(os, 'chown'):
            os.chown(temporary, metadata.st_uid, metadata.st_gid)
        temporary.chmod(metadata.st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def install(root, backup, changes, activate, before_rollback=None):
    """Stopped-service file transaction; restore all bytes if activation fails."""
    originals = {}
    for name, row in changes.items():
        path = root / name
        originals[name] = read_regular(path) if row['before'] is not None else None
        if originals[name] is not None:
            need(digest(originals[name]) == row['before'], 'module_changed_before_install')
            (backup / name).write_bytes(originals[name])
        else:
            need(not path.exists() and not path.is_symlink(), 'new_module_already_exists')
    written = []
    try:
        for name, row in changes.items():
            path = root / name
            replace_file(path, row['content'].encode('utf-8'), path if path.exists() else root / 'app.py')
            written.append(name)
        activate()
    except RollbackBlocked:
        raise
    except BaseException:
        if before_rollback is not None:
            before_rollback()
        for name in reversed(written):
            path = root / name
            if originals[name] is None:
                path.unlink()
            else:
                replace_file(path, originals[name], path)
        raise


def systemctl(*args):
    result = subprocess.run(['systemctl', *args], capture_output=True, timeout=60)
    need(result.returncode == 0, 'service_operation_failed')
    return result.stdout.decode().strip()


def require_stopped_services():
    try:
        for service in SERVICES:
            state = systemctl('show', service, '--property=ActiveState', '--value')
            main_pid = systemctl('show', service, '--property=MainPID', '--value')
            control_pid = systemctl('show', service, '--property=ControlPID', '--value')
            if state not in {'inactive', 'failed'} or main_pid != '0' or control_pid != '0':
                raise ServiceRollbackBlocked('rollback_requires_service_quiescence')
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        raise ServiceRollbackBlocked('rollback_requires_service_quiescence') from error


@contextmanager
def activated_services():
    try:
        # A start failure can still leave one of the two services running.
        systemctl('start', *SERVICES)
        yield
    except BaseException:
        try:
            systemctl('stop', *SERVICES)
        except (RuntimeError, OSError, subprocess.SubprocessError) as error:
            raise ServiceRollbackBlocked('rollback_requires_service_quiescence') from error
        require_stopped_services()
        raise


def request(path, *, include_headers=False):
    req = urllib.request.Request(PUBLIC + path, headers={'Cache-Control': 'no-cache'})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read(1024 * 1024 + 1)
            need(len(raw) <= 1024 * 1024, 'unexpected_public_response_size')
            result = (response.status, raw)
            return (*result, dict(response.headers)) if include_headers else result
    except urllib.error.HTTPError as error:
        result = (error.code, b'')
        return (*result, dict(error.headers)) if include_headers else result


def owner_password_health():
    status, raw, headers = request('/auth/owner/status', include_headers=True)
    need(status == 200, 'owner_password_status_unavailable')
    value = json.loads(raw)
    need(isinstance(value, dict) and type(value.get('configured')) is bool
         and value.get('method') == 'password'
         and value.get('setup_requires') == 'existing_owner_session_or_bootstrap'
         and value.get('min_password_length') == 10 and value.get('max_password_bytes') == 128,
         'owner_password_contract_changed')
    normalized = {name.lower(): content for name, content in headers.items()}
    need('no-store' in normalized.get('cache-control', '')
         and normalized.get('x-content-type-options') == 'nosniff',
         'owner_password_privacy_headers_missing')
    # GET verifies route existence without enrollment, failed-password attempts,
    # throttle counters, tokens or any modification of the owner's credentials.
    for path in ('/auth/owner/setup', '/auth/owner/login', '/auth/owner/password'):
        need(request(path)[0] == 405, 'owner_password_write_route_missing')
    return value['configured']


def owner_binding(database):
    """Compare only the established identity, never passwords or broker tokens."""
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
        need(db.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'database_integrity_failed')
        registry = db.execute('SELECT singleton,telegram_sub,policy_version FROM installation_owner').fetchall()
        users = db.execute('SELECT id,telegram_sub FROM users ORDER BY id').fetchall()
    need(len(registry) == 1 and len(users) <= 1, 'owner_identity_invalid')
    return digest(json.dumps({'registry': registry, 'users': users}, sort_keys=True).encode())


def protect_compatible_rollback(root, database, expected, configuration_before, binding_before):
    """A957 already supports password login; preserve its unchanged authentication code.

    The change allowlist excludes all auth, configuration and migration modules.
    Never restore the database or credentials, even after failed activation.
    """
    require_stopped_services()
    try:
        need(digest(read_regular(CONFIGURATION)) == configuration_before,
             'owner_configuration_changed')
        need(owner_binding(database) == binding_before, 'owner_binding_changed')
        verify_unchanged_modules(root, expected)
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=15)) as db:
            need(db.execute('PRAGMA journal_mode').fetchone()[0] == 'wal', 'database_mode_changed')
    except (RuntimeError, sqlite3.Error, OSError) as error:
        raise CompatibleRollbackBlocked('compatible_source_recovery_not_proven') from error


def backup_database(database, target):
    """SQLite backup includes committed WAL pages; never copy only the main DB file."""
    need(not target.exists() and not target.is_symlink(), 'backup_already_exists')
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=15)) as source:
        need(source.execute('PRAGMA journal_mode').fetchone()[0] == 'wal', 'database_mode_changed')
        with closing(sqlite3.connect(target)) as saved:
            source.backup(saved)
            need(saved.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'backup_integrity_failed')
    need(owner_binding(target) == owner_binding(database), 'backup_owner_binding_changed')


def decision_schema_status(database):
    """Observe committed decision-journal schema and count; never read its payloads."""
    table = 'portfolio_decision_cycles'
    index = 'portfolio_decision_cycles_latest'
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=15)) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        objects = set(db.execute('SELECT name,type,tbl_name FROM sqlite_master WHERE name IN (?,?)',
                                 (table, index)).fetchall())
        need(objects == {(table, 'table', table), (index, 'index', table)},
             'decision_journal_schema_missing')
        rows = db.execute('SELECT count(*) FROM portfolio_decision_cycles').fetchone()[0]
    return {'decision_journal_ready': True, 'decision_journal_rows': rows}


def healthy():
    status, raw = request('/health')
    need(status == 200 and json.loads(raw) == {'status': 'ok'}, 'runtime_health_failed')
    need(request('/workspace/live?wait=0')[0] == 401, 'runtime_authentication_changed')
    for service in SERVICES:
        need(systemctl('is-active', service) == 'active', 'runtime_service_inactive')


def database_path():
    result = Path('/var/lib/analyst-ai/backend.db')
    for line in CONFIGURATION.read_text().splitlines():
        key, separator, value = line.partition('=')
        if key == 'DATABASE_PATH' and separator:
            fields = shlex.split(value)
            need(len(fields) == 1, 'invalid_database_configuration')
            result = Path(fields[0])
    need(result.is_file() and not result.is_symlink() and result.resolve(strict=True) == result
         and result.is_relative_to('/var/lib/analyst-ai'), 'unsafe_database_location')
    return result


def run(envelope):
    import fcntl
    need(os.getuid() == 0, 'runtime_deployment_identity_required')
    bundle = envelope['payload']
    validate(bundle)
    dependency = dependency_entries(bundle['pdf_dependency'])
    root = Path('/opt/analyst-ai/backend')
    run_id = envelope['run_id']
    need(re.fullmatch('[0-9]{8,20}', run_id), 'invalid_run_id')
    parent = Path('/var/lib')
    need(parent.resolve(strict=True) == parent and parent.stat().st_uid == 0
         and not parent.stat().st_mode & 0o022, 'unsafe_archive_parent')
    archive = parent / ('analyst-ai-decision-engine-' + run_id)
    with Path('/var/lock/analyst-ai-plan-development.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        verify_base(root, bundle['expected'], bundle['files'])
        verify_dependency(root, dependency)
        healthy()
        owner_configured_before = owner_password_health()
        policy_path = '/client/update-policy?package_name=ru.omnicio.app.debug'
        policy_status, policy_before = request(policy_path)
        need(policy_status == 200, 'apk_policy_unavailable')
        old_pids = {service: systemctl('show', service, '--property=MainPID', '--value')
                    for service in SERVICES}
        database = database_path()
        configuration_before = digest(read_regular(CONFIGURATION))
        binding_before = owner_binding(database)
        archive.mkdir(mode=0o700)
        need(archive.resolve(strict=True) == archive and not archive.stat().st_mode & 0o077,
             'unsafe_archive_directory')
        backup = archive / 'previous-source'
        backup.mkdir(mode=0o700)
        (archive / 'source-bundle.json').write_text(json.dumps(bundle), encoding='utf-8')
        vendor = None
        journal_status = {}
        try:
            systemctl('stop', *SERVICES)
            require_stopped_services()
            verify_base(root, bundle['expected'], bundle['files'])
            backup_database(database, archive / 'before.sqlite3')

            def activate():
                for name, row in bundle['files'].items():
                    need(digest(read_regular(root / name)) == row['after'],
                         'installed_source_verification_failed')
                with activated_services():
                    for attempt in range(8):
                        try:
                            healthy()
                            break
                        except (RuntimeError, urllib.error.URLError):
                            if attempt == 7:
                                raise
                            time.sleep(2)
                    for service in SERVICES:
                        need(systemctl('show', service, '--property=MainPID', '--value') not in {'0', old_pids[service]},
                             'runtime_process_not_replaced')
                    need(request('/workspace/version')[0] == 401, 'version_endpoint_authentication_changed')
                    need(request('/workspace/presentation')[0] == 401, 'presentation_endpoint_authentication_changed')
                    need(request('/workspace/osint/status')[0] == 401, 'osint_endpoint_authentication_changed')
                    need(request('/workspace/strategy')[0] == 401, 'strategy_endpoint_authentication_changed')
                    need(request('/automation/decisions')[0] == 401, 'decisions_endpoint_authentication_changed')
                    need(request('/automation/strategy-plan')[0] == 401, 'strategy_plan_authentication_changed')
                    need(request(policy_path) == (policy_status, policy_before), 'apk_policy_changed')
                    need(owner_password_health() == owner_configured_before, 'owner_auth_configuration_changed')
                    verify_unchanged_modules(root, bundle['expected'])
                    need(digest(read_regular(CONFIGURATION)) == configuration_before,
                         'owner_configuration_changed')
                    need(owner_binding(database) == binding_before, 'owner_binding_changed')
                    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=15)) as db:
                        need(db.execute('PRAGMA journal_mode').fetchone()[0] == 'wal', 'database_mode_changed')
                    journal_status.update(decision_schema_status(database))

            install(root, backup, bundle['files'], activate,
                    before_rollback=lambda: protect_compatible_rollback(
                        root, database, bundle['expected'], configuration_before, binding_before))
        except RollbackBlocked as error:
            # Activation already handles failed-service shutdown. Do not stop a
            # healthy service solely because rollback is blocked, restore the DB,
            # delete credential guards, or restart code without password support.
            (archive / 'failure.json').write_text(json.dumps({
                'status': 'failed', 'code': str(error),
                'previous_service_restarted': False, 'installed_files_preserved': True,
                'rollback_performed': False,
                'owner_credentials_preserved': True, 'database_restored': False,
            }))
            raise
        except BaseException:
            if vendor is not None:
                shutil.rmtree(vendor)
            systemctl('start', *SERVICES)
            healthy()
            (archive / 'failure.json').write_text(json.dumps({'status': 'failed', 'previous_service_restarted': True}))
            raise
        installed = {name: digest(read_regular(root / name)) for name in bundle['files']}
        need(all(installed[name] == row['after'] for name, row in bundle['files'].items()),
             'installed_source_verification_failed')
        receipt = {'schema': 1, 'status': 'deployed', 'server_id': 9417611,
                   'source_commit': bundle['source_commit'], 'test_run_id': bundle['run_id'],
                   'deployment_run_id': run_id, 'installed_sha256': installed,
                   'checked_at_utc': datetime.now(timezone.utc).isoformat(),
                   'health': 200, 'unauthenticated_live': 401, 'unauthenticated_version': 401, 'unauthenticated_presentation': 401, 'unauthenticated_osint': 401, 'unauthenticated_strategy': 401, 'unauthenticated_decisions': 401,
                   'pdf_dependency_sha256': bundle['pdf_dependency']['sha256'],
                   'apk_policy_sha256': digest(policy_before), 'apk_changed': False,
                   'database_backup_created': True, 'tests_executed_on_timeweb': False,
                   'owner_password_status': 200, 'owner_password_write_routes_get': 405,
                   'owner_binding_preserved': True, 'owner_configuration_preserved': True,
                   'database_restored': False, 'compatible_password_baseline_preserved': True, 'database_journal_mode': 'wal',
                   'physical_phone_verified': False, **journal_status}
        (archive / 'deployment.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    try:
        run(ENVELOPE)
    except Exception as error:
        code = str(error)
        if re.fullmatch('[a-z_]{1,100}', code) is None:
            code = type(error).__name__
        print(json.dumps({'status': 'failed', 'code': code, 'server_id': 9417611}), flush=True)
        raise



