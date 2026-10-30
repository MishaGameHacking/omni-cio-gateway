"""One-shot restart of the unchanged cc22 runtime after a failed health check.

No application import, source/configuration edit, DB restore, model request or
broker call. Only the two existing systemd services may be stopped/started.
"""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request

BASE = 'af95e8de8cfd50970d712483b8c17e866f7239c9'
BASELINE_BLOBS = {
 "ai_broker_access.py": "b182ad2310f39a518ff329c91ed4fa81a465d1a1",
 "ai_budget.py": "36ae45ae5d7b33c55b3dee614c9ead9ea41f575a",
 "ai_guarded_client.py": "28634a5f69ffa16fa0d7b485a62f7bd1c4e2ffb6",
 "ai_jobs.py": "9369978cffdc79c3498727676786657ca4f091e1",
 "ai_policy.py": "4940ab8c903a55cf74e07fe93499dd2745e95e87",
 "ai_route_catalog.py": "4da2c6d3f8f808a44df1201448b5451772847181",
 "allocation_plan.py": "08f8741031ec28b44271d0c8f247602fd9a5ec73",
 "analysis_engine.py": "3552f85ff993e4eba231fe3536f60e476fc32109",
 "android_runtime_contract.py": "2bece677b34096d526363d0ec4644ae7c2eaf784",
 "app.py": "a68eef110e6efbfb521316ec84244b46801c997a",
 "application_hierarchy.py": "b8f34906b5799b1ae3eb17a8b2f06ce0ba2e9c16",
 "automation_ui_evidence.py": "29e11a710baa7a116a5fe5b9163c8d45e9e54c6e",
 "autonomous_ai.py": "7d3796b749953f339fe605f4c73660d62c8851a2",
 "autonomous_controller.py": "1274f36cdd77d3b5ebae5bb0424034816b9a7c3d",
 "background_dispatch.py": "260a231db15d27c37c577e12d4b6170e26bdffe3",
 "bounded_ai_response.py": "f4c7c4dd79fe49f9ed0d9549750a5d1ddb9ce619",
 "broker_connections.py": "fd7367f0c4e8a6fccca9c73f22fa9c31c16ed361",
 "client_compatibility.py": "85d75d67a51e386d8eb15356b36a1cb16ccef646",
 "client_diagnostics.py": "c9c674923c58abefcdc81b70c34fdb03ee7ce752",
 "client_updates.py": "5c89c98f122944d50117b527551f0f649693dfac",
 "credit_evidence.py": "26a58c95dfec7827c1d7abac956da9dbf4069916",
 "decision_cycle.py": "a8c04d59e877b620802ca3d24e4049be0bf0bb52",
 "decision_views.py": "a66870bab806e6c8ecadd05bf8c4613cea29c9c2",
 "event_monitor.py": "10c41c8453a56c2474612fa3d99ec0643de8c7ec",
 "evidence_history.py": "1d0ca9492d2f44937b320db94585baf8696c7e62",
 "evidence_order.py": "5e6dcc8d08ce021e7634c5d8235c0f8e63d17adc",
 "evidence_revision.py": "0546a469986c6e2a0ac18a9335ec177e6d54166f",
 "fund_policy.py": "ce74b404ae1d48d484f2030ee1c4a3059fe982cc",
 "installation_evidence.py": "9ed34abec5eada18aabd1f9a7d72d4d2ae32dfeb",
 "investment_chat_policy.py": "29b7f4198d5be78bd578b407df9acf58d6b851e9",
 "investment_links.py": "8d4787e92222ded57aef85d9754749bee270b83d",
 "margin_policy.py": "378c600e31288af87f5bf8ea8814cbf95b468ac8",
 "market_schedule.py": "f72f8660fc75429b96f7d47ad8f14b218961a4da",
 "model_json_limits.py": "8ca718100438d87b7eda02bb04af25a1b7f42c5e",
 "monitoring_access.py": "6e098617d9c14eab067c9e1b46c0ef2f0dcad49f",
 "operations_ledger.py": "8e93b7b52e39360b11631e5fca73ec2440a3270e",
 "order_lifecycle.py": "5752442e4f8dfce84a499eeab219234633b029ff",
 "osint_analysis.py": "e5f8a3edd7985d4980d5cfd9cce7beadbad7d034",
 "osint_api.py": "118dfe55a7a06f916255bae2978840fd6da3c057",
 "osint_catalogue.py": "55ac056a9adf7ec80155742348899b7a3f15a1a4",
 "osint_content.py": "2064569884391adb2000f79401c91875f3e46ad3",
 "osint_network.py": "1d51fd70d5dab4de17c0e6fdab02889d8cd8ee8f",
 "osint_pdf.py": "5e9792e9f4c1da9c8f13695cf2fc4fcae038765f",
 "osint_read.py": "2c694d0a3ba391e10022314ca4f4196738e5f54a",
 "osint_retention.py": "7dd03ab7e8b1e75905fd149fdb7de5c0265a4843",
 "osint_store.py": "a18e63f7a0dbd8d5b1622100a63b2f3ab407040e",
 "osint_worker.py": "560a1c37325741852d8d8a2576e3b96bc5892532",
 "owner_access.py": "4062f1ebfc86a31e3152d143db5bd9ccf2dbc52e",
 "owner_app.py": "eea3a5e8ddeccd08fa8bb960e15b1a1f4e2d04e6",
 "owner_password.py": "69314e8501e26db9ab02cc5b1d4b268a39d2a11d",
 "owner_password_routes.py": "53bc9984fbd5cc52c3fb729ce8e5d0fe271b2501",
 "paper_execution.py": "e40cda179dcbc66cce157d93ceccf600202d090b",
 "portfolio_accounting.py": "6db02da95cf24119042175c4ff849665cfdeaf2e",
 "portfolio_details.py": "468d6765f89fd006c3d2521b0de1cbfafd959835",
 "portfolio_mandate.py": "b92ff53e83dae171da7887256c8c19435110339d",
 "portfolio_research.py": "7ca34284f1569f6df4f946740b6d0aeda83f6e7a",
 "portfolio_risk.py": "d5a72e23e4c53d287877a4301c0a2035b37602b2",
 "portfolio_scenarios.py": "0d887e38ed07d968294342852cd05dad70f01590",
 "public_sources.py": "486d7f27d395780b05abd49ff42560425fcc5719",
 "public_updates_app.py": "1bbca2b2e59501517d37331b2a475d9195d898c3",
 "purchase_policy.py": "dacfcb4f4778d58013aaaca76e6c2c5d9ad3c059",
 "release_bytes.py": "608bd9fd410736d24f45b46c622b0632f0fc0ebd",
 "release_contract.py": "3ba25146f780d1cc0eee86465e7cf6c73b32af14",
 "release_json.py": "787697b5b86b6b698ba9757440f9fe3b31a0c932",
 "release_lock.py": "3859f3e4c5397c44e44b0dbd1e320c8957360142",
 "release_publication.py": "48bf41cddf2926617683b9d40a7f29c35c43ca99",
 "requirements.txt": "d420bbaf69f3c79f0b4959ed1dd014a4aaffaa7d",
 "research_clock.py": "36ec6b0a8ff0f7cfa44a4d11795b592e22cb2e79",
 "research_import.py": "224f9aed83859f8a963f96b7a51a7582e750aa8a",
 "research_profile_cache.py": "a2050a709ec8588618f73472beaebeea5ee48608",
 "research_snapshot.py": "97ce21b8ca82662bbd6866d1f458eb1259c8065d",
 "research_store.py": "9e6473ed3ec97c39bede49a20f26f3ad7cc1edb9",
 "risk_math.py": "15528c208b96c7aa5fa3ca1bde3aebc1e95fe1b4",
 "risk_preview.py": "d3743b5a51adeed6eb29b86b6be5bcbb6014e793",
 "schema_migrations.py": "2c7f03cebc3f3ddb92c34a56249611bf3abaca0a",
 "server_version.py": "54f0c33521ef77153b8809450be2039ddb9e0dd6",
 "source_observability.py": "c174a21b71c81ddc5cd3e829b0b16e32d1a8ed99",
 "strategy_actions.py": "63ec7ff60adf983bc60b19b7ad66630c2445bf45",
 "strategy_activity.py": "d8d102900149db2edb0b5309c242c7d31941877a",
 "strategy_construction.py": "fd88ca5173a5be2e6555f0bec49d16b9d0342a8d",
 "strategy_profiles.py": "6f2f3f5d8f7ef6ed495d7c175c165e1bd8047156",
 "strategy_sales.py": "e1de62854972c8bb556554c7e438c9e0ce2dfc07",
 "strategy_yield.py": "dc0f0464b6f651b915c0a1b54f6bea84726d1136",
 "telegram_browser_app.py": "04f0def718aeadd1dc3a96e09abc4ebd3964b31b",
 "telegram_oidc.py": "3e9c735dbf8b3dca7fa18626a05e480b67125f9f",
 "timeweb_ai.py": "4378b4dfa8d3bd9a30b6c838b3480f7a1bb0b34c",
 "tinvest_portfolio.py": "ab2eb927df7e38806f64518fcf13962a30c04b22",
 "volume.py": "d2eba4cb88620ef1069cbc1f2b0eaeffb4d1ba20",
 "volume_analysis.py": "ca9545390ab3f5abcdcfb7f6c058476d12a8fed0",
 "volume_catalogue.py": "eb7b2d9bb8b7e458b206e30866cdf1d93d1bbb65",
 "volume_chat.py": "1ae48f7c5af450e548d311b1ff207b94f7b0ee98",
 "volume_contract.py": "f31abae3e42896fab46b25a9bdfc5f702e64d7ae",
 "volume_credit.py": "4c9c23ea0bc8d192eae39744f9c6d51de0e4a952",
 "volume_devices.py": "187d82bc3e970883662521ab7119a7accba1fa5e",
 "volume_explanations.py": "ea75cd04d96ee791aa6f3d7bb6db04d9513b404a",
 "volume_impact.py": "34545497358d8718e9e2860b4d070293e48285bb",
 "volume_jobs.py": "d9e05ccd561d0122eb620d0bb2ed03a90d751a8b",
 "volume_live.py": "3ce2fa9c483e0b4d27c75471fb498df43835cb0f",
 "volume_market.py": "0fe5e5930fe66c1ac2fc36353c1ba05f274a6d3c",
 "volume_monitor.py": "63574cc38115c8447468c000ade6142f9dc77108",
 "volume_news.py": "857aef1d19bb20a25edf543bde5c85ad9f72c5bf",
 "volume_notifications.py": "32ba592be696c31219b46ad935ebc5d05c84c37d",
 "volume_plans.py": "eada38c394aea69758b54f26565cfae5f5649dd0",
 "volume_presentation.py": "6dc0466fd685908bd338e1c95f9e54338cd38438",
 "volume_purchases.py": "51a8e7a69a5743d48dd9b1b54151f206300e81b7",
 "volume_state.py": "14c6931a4b4ea9e9c865fca5decca4ceb13d11e4",
 "volume_workspace.py": "baeab2ad04dc6b08d24e05efd115d511de17c920",
 "workspace_readiness.py": "1c35534a9ad9711dac0cf564b848aa49787e684b"
}
ROOT = Path('/opt/analyst-ai/backend')
CONFIGURATION = Path('/etc/analyst-ai/backend.env')
DATABASE = Path('/var/lib/analyst-ai/backend.db')
ARCHIVES = Path('/var/lib')
UNIT_ROOT = Path('/etc/systemd/system')
LOCK = Path('/var/lock/analyst-ai-plan-development.lock')
SERVICES = ('analyst-ai-owner.service', 'analyst-ai-updates.service')
ENDPOINTS = {
    'local_health': 'http://127.0.0.1:8080/health',
    'public_health': 'https://analyst-ai-2941515.twc1.net/health',
    'public_password': 'https://analyst-ai-2941515.twc1.net/auth/owner/status',
}
PHASES = frozenset({'validate', 'preflight', 'stop', 'backup', 'start', 'health', 'preservation', 'done'})


def need(value, code):
    if not value:
        raise RuntimeError(code)


def regular(path):
    need(path.is_file() and not path.is_symlink() and path.resolve(strict=True) == path
         and path.stat().st_nlink == 1, 'recovery_regular_file_required')
    return path.read_bytes()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git_blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def baseline():
    need(ROOT.is_dir() and ROOT.resolve(strict=True) == ROOT, 'recovery_runtime_path_changed')
    for name, expected in BASELINE_BLOBS.items():
        need(git_blob(regular(ROOT / name)) == expected, 'recovery_source_baseline_changed')


def database_identity():
    need(DATABASE.is_file() and not DATABASE.is_symlink() and DATABASE.resolve(strict=True) == DATABASE
         and DATABASE.stat().st_nlink == 1, 'recovery_database_path_changed')
    info = DATABASE.stat()
    with closing(sqlite3.connect(DATABASE.as_uri() + '?mode=ro', uri=True, timeout=3)) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        need(db.execute('PRAGMA journal_mode').fetchone()[0] == 'wal', 'recovery_database_not_wal')
        owner = db.execute('SELECT singleton,telegram_sub,policy_version FROM installation_owner').fetchall()
        users = db.execute('SELECT id,telegram_sub,tinvest_token_encrypted FROM users ORDER BY id').fetchall()
        credentials = db.execute('SELECT * FROM owner_password_credentials ORDER BY user_id').fetchall()
        need(len(owner) == len(users) == len(credentials) == 1, 'recovery_owner_binding_invalid')
    # Private in-memory fingerprints only; neither values nor hashes are receipts.
    return (info.st_dev, info.st_ino, sha(repr((owner, users, credentials)).encode()))


def ctl(*args, timeout=10):
    result = subprocess.run(['systemctl', *args], capture_output=True, timeout=timeout)
    need(result.returncode == 0, 'recovery_service_command_failed')
    return result.stdout.decode('utf-8').strip()


def service_identity():
    result = {}
    total_stop_seconds = 0
    for service in SERVICES:
        value = ctl('show', service, '--property=TimeoutStopUSec', '--value')
        need(re.fullmatch(r'(?:[0-9]+(?:min|s) ?)+', value) is not None,
             'recovery_service_stop_timeout_unbounded')
        seconds = sum(int(number) * (60 if unit == 'min' else 1)
                      for number, unit in re.findall(r'([0-9]+)(min|s)', value))
        need(0 < seconds <= 120, 'recovery_service_stop_timeout_unbounded')
        total_stop_seconds += seconds
        need(total_stop_seconds + 10 <= 180, 'recovery_combined_stop_timeout_unbounded')
        fragment = Path(ctl('show', service, '--property=FragmentPath', '--value'))
        need(fragment == UNIT_ROOT / service, 'recovery_service_identity_changed')
        result[service] = sha(regular(fragment))
    return result


def pids():
    result = {}
    for service in SERVICES:
        value = ctl('show', service, '--property=MainPID', '--value')
        need(value.isdecimal(), 'recovery_service_pid_invalid')
        result[service] = int(value)
    return result


def stopped():
    for service in SERVICES:
        state = ctl('show', service, '--property=ActiveState', '--value')
        main = ctl('show', service, '--property=MainPID', '--value')
        control = ctl('show', service, '--property=ControlPID', '--value')
        need(state in {'inactive', 'failed'} and main == control == '0', 'recovery_services_not_stopped')


def probe(name):
    begin = time.monotonic()
    result = {'endpoint': name, 'ok': False}
    try:
        request = urllib.request.Request(ENDPOINTS[name], headers={'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read(16385)
            need(len(raw) <= 16384, 'recovery_health_body_too_large')
            value = json.loads(raw)
            result['http_status'] = response.status
            if name == 'public_password':
                result['ok'] = (response.status == 200 and isinstance(value, dict)
                    and value.get('configured') is True and value.get('method') == 'password'
                    and 'no-store' in response.headers.get('Cache-Control', ''))
            else:
                result['ok'] = response.status == 200 and value == {'status': 'ok'}
    except urllib.error.HTTPError as error:
        result['http_status'] = error.code
        result['error'] = 'HTTPError'
    except (OSError, ValueError, RuntimeError) as error:
        result['error'] = type(error).__name__ if type(error).__name__ in {
            'TimeoutError', 'URLError', 'JSONDecodeError', 'RuntimeError', 'OSError'} else 'health_error'
    result['elapsed_ms'] = round((time.monotonic() - begin) * 1000)
    return result


def verify_health():
    latest = []
    for attempt in range(4):
        latest = [probe(name) for name in ENDPOINTS]
        if all(row['ok'] for row in latest):
            return latest
        if attempt < 3:
            time.sleep(1)
    raise RuntimeError('recovery_health_not_restored')


def backup(target):
    need(not target.exists() and not target.is_symlink(), 'recovery_backup_already_exists')
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    deadline = time.monotonic() + 20
    def progress(_status, _remaining, _total):
        need(time.monotonic() < deadline, 'recovery_backup_deadline')
    with closing(sqlite3.connect(DATABASE.as_uri() + '?mode=ro', uri=True, timeout=3)) as source:
        with closing(sqlite3.connect(target)) as saved:
            source.backup(saved, pages=256, progress=progress, sleep=0.01)


def unchanged(configuration, identity, units):
    baseline()
    need(sha(regular(CONFIGURATION)) == configuration, 'recovery_configuration_changed')
    need(database_identity() == identity, 'recovery_database_or_owner_binding_changed')
    need(service_identity() == units, 'recovery_service_identity_changed')


def error_receipt(error, phase):
    # No exception message, source text, locals, paths or secret-derived hashes.
    frames = []
    trace = error.__traceback__
    while trace is not None:
        code = trace.tb_frame.f_code
        if (code.co_filename == 'owner-plan-operation'
                and re.fullmatch('[A-Za-z_][A-Za-z_0-9]{0,63}', code.co_name)):
            frames.append({'function': code.co_name, 'line': trace.tb_lineno})
        trace = trace.tb_next
    return {'status': 'failed', 'phase': phase if phase in PHASES else 'unknown',
            'error': type(error).__name__ if type(error).__name__ in {
                'RuntimeError', 'TimeoutError', 'TimeoutExpired', 'OperationalError',
                'OSError', 'URLError', 'KeyboardInterrupt'} else 'recovery_error',
            'frames': frames, 'database_restored': False, 'source_modified': False,
            'configuration_modified': False, 'server_id': 9417611}


def validate_archive_parent():
    need(ARCHIVES.resolve(strict=True) == ARCHIVES and ARCHIVES.stat().st_uid == 0
         and not ARCHIVES.stat().st_mode & 0o022, 'recovery_archive_parent_invalid')


def recover_locked(envelope):
    phase = 'validate'
    archive = None
    stop_attempted = False
    try:
        need(os.getuid() == 0 and envelope['payload'] == {'source_commit': BASE}, 'recovery_identity_invalid')
        run = str(envelope['run_id'])
        need(re.fullmatch('[1-9][0-9]{7,19}', run) is not None, 'recovery_run_invalid')
        baseline()
        configuration, identity, units = sha(regular(CONFIGURATION)), database_identity(), service_identity()
        old_pids = pids()
        phase = 'preflight'
        before = [probe(name) for name in ENDPOINTS]
        if before[0]['ok']:
            receipt = {'status': 'restart_not_needed', 'server_id': 9417611, 'source_commit': BASE,
                       'health': before, 'source_modified': False, 'database_restored': False}
            print(json.dumps(receipt), flush=True)
            return receipt
        validate_archive_parent()
        candidate = ARCHIVES / ('analyst-ai-runtime-recovery-' + run)
        candidate.mkdir(mode=0o700)
        archive = candidate
        phase = 'stop'
        stop_attempted = True
        ctl('stop', *SERVICES, timeout=180)
        stopped()
        unchanged(configuration, identity, units)
        phase = 'backup'
        backup(archive / 'before.sqlite3')
        phase = 'start'
        ctl('start', *SERVICES, timeout=60)
        phase = 'health'
        after = verify_health()
        new_pids = pids()
        need(all(new_pids[name] > 0 and new_pids[name] != old_pids[name] for name in SERVICES),
             'recovery_process_not_replaced')
        phase = 'preservation'
        unchanged(configuration, identity, units)
        receipt = {'status': 'recovered', 'server_id': 9417611, 'source_commit': BASE,
            'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'before': before, 'after': after,
            'pids_replaced': True, 'source_modified': False, 'configuration_modified': False,
            'owner_and_password_preserved': True, 'broker_binding_preserved': True,
            'database_inode_preserved': True, 'database_restored': False, 'database_journal_mode': 'wal',
            'backup_created': True, 'model_job_enqueued': False, 'trading_configuration_changed': False}
        (archive / 'recovery.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt), flush=True)
        return receipt
    except BaseException as error:
        receipt = error_receipt(error, phase)
        if stop_attempted:
            try:
                unchanged(configuration, identity, units)
                ctl('start', *SERVICES, timeout=60)
                receipt['recovery_start_requested'] = True
            except BaseException:
                receipt['recovery_start_requested'] = False
        if archive is not None:
            try:
                (archive / 'failure.json').write_text(json.dumps(receipt, indent=2) + '\n')
            except OSError:
                receipt['failure_record_saved'] = False
        print(json.dumps(receipt), flush=True)
        raise


def recover(envelope):
    import fcntl
    with LOCK.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return recover_locked(envelope)


if __name__ == '__main__':
    recover(ENVELOPE)
