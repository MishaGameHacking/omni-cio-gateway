"""Bounded read-only active route/entrypoint observation; no application import.

No environment, private database, session, application log, arbitrary command or
complete service/configuration/source text is exported. Only allowlisted route
tokens and invocation fields can leave the process. Unknown values stay unknown.
"""
from __future__ import annotations

import datetime
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import shlex
import stat
import subprocess
import sys
import time

EXPECTED = {'prior_observation_sha256': '599df7ca37ab4cc9a98effdf4a2688911e6d0225edf762d0d72298d0e954f477', 'reference44_source_sha256': 'e34b717fa408fbe377d910a372933c35a2ba1bdddf02263b6daa477df70f93b9', 'active_caddy': {'bytes': 933, 'sha256': '57192fc11c94c8691c036d6208ce20ab429a5af7047ea17f3432498212db3041'}, 'sources': {'/opt/analyst-ai/backend/ai_budget.py': {'bytes': 11358, 'sha256': '7fa2a785f26e1227252c8785f1e12029192b093ad2809a020f1cd647f7bcf947'}, '/opt/analyst-ai/backend/ai_guarded_client.py': {'bytes': 16889, 'sha256': '349f89534b0e562aaf84a6bdbce9db28db5a9719cd3682ba3bf23daaec2d59ae'}, '/opt/analyst-ai/backend/ai_jobs.py': {'bytes': 10904, 'sha256': '38205417d64d14847620a4f45a2a20ad1f0d7cd5bab512c1feca8bfd53a45194'}, '/opt/analyst-ai/backend/ai_policy.py': {'bytes': 5269, 'sha256': '44cfdcdf2d862a681287f2a20dc387051fe227dcb2c68d5d18247d349a714fa9'}, '/opt/analyst-ai/backend/ai_route_catalog.py': {'bytes': 4865, 'sha256': 'a88981df52942a4c08fd60018aabf333ceaa85e8c4db8e79930f75b5e9e5a3c9'}, '/opt/analyst-ai/backend/allocation_plan.py': {'bytes': 14103, 'sha256': '90f3396a685ef9968c30fa5c5c1f7acfb9983825993d4c0b9b68710ce07fd4ad'}, '/opt/analyst-ai/backend/analysis_engine.py': {'bytes': 11660, 'sha256': '2700fdde343666a6e2441a943fb11dac2a5ea3906c04520b90c2b2721bde22e1'}, '/opt/analyst-ai/backend/android_runtime_contract.py': {'bytes': 3142, 'sha256': '1ed9a56769d308c9f5457fa383517a80965cd474dff8851e16a85390954335c2'}, '/opt/analyst-ai/backend/app.py': {'bytes': 29265, 'sha256': '33950c712e6442ce00af8de84f1e2c174c75d140728c1c093f00d717f5948c40'}, '/opt/analyst-ai/backend/automation_ui_evidence.py': {'bytes': 8099, 'sha256': '4a06b75ba342d80f7bcee6d0fbbb985d6562d390deb147438c04c48be91ae35c'}, '/opt/analyst-ai/backend/autonomous_ai.py': {'bytes': 53552, 'sha256': '789e338b462021f5d0274ae438638f54257111dbaadbee4dde090e130aa647cf'}, '/opt/analyst-ai/backend/autonomous_controller.py': {'bytes': 35217, 'sha256': '1994204de29b2569843d4d47012bbc372716d9d9db6c33daf058d73ae18600eb'}, '/opt/analyst-ai/backend/bounded_ai_response.py': {'bytes': 4723, 'sha256': '95d51fa2f6a2c6190ae572a2c88cf13ca2803af999d9a77ddfd908c6c397db14'}, '/opt/analyst-ai/backend/broker_connections.py': {'bytes': 6568, 'sha256': 'd0e4079f030ccc466da0b5224478a75841c02cfbf17a1151286a5f56845f5651'}, '/opt/analyst-ai/backend/client_compatibility.py': {'bytes': 2245, 'sha256': 'cf585f4a740198325e47166b318f12c41017491e34edb27c5511c53790a7d8e9'}, '/opt/analyst-ai/backend/client_diagnostics.py': {'bytes': 8863, 'sha256': '6316faa45abc793adb16fb6d8b42993e2c778e9411e31ed525c1742c379e1bc0'}, '/opt/analyst-ai/backend/client_updates.py': {'bytes': 13743, 'sha256': '79c1f8670cc61f94f917c9ad4b6e394f1430a08b61b8ef87216624fec12b9184'}, '/opt/analyst-ai/backend/credit_evidence.py': {'bytes': 15694, 'sha256': '96af887aa723e8e74e7d037f4785da532d6aa16ef6916eaf099c0ba847b4fd80'}, '/opt/analyst-ai/backend/evidence_history.py': {'bytes': 3273, 'sha256': 'e9f16324ac661abfcd4c8ee6e6deaa7b7748245891e8c5c5c15d02c63a28ce12'}, '/opt/analyst-ai/backend/evidence_order.py': {'bytes': 3041, 'sha256': '46368a7a78a2fbfc55198e222795abe977c490c3f07703ddcb8f4afd2f45f2d7'}, '/opt/analyst-ai/backend/evidence_revision.py': {'bytes': 3100, 'sha256': '7fa8f33904ac8f363f7eaddbba29ff9942ce7e1e4ad958ad23fc1185852876c4'}, '/opt/analyst-ai/backend/installation_evidence.py': {'bytes': 8652, 'sha256': '04e13002c8b5e5046a86e3a5e8de1edc354888eb581202f010ee992563468c3c'}, '/opt/analyst-ai/backend/investment_chat_policy.py': {'bytes': 9474, 'sha256': '65130e31014142a968546beeebd58d93422c7f7ff027b34f587a890002f529f2'}, '/opt/analyst-ai/backend/investment_links.py': {'bytes': 1418, 'sha256': '55d7d36ab4847509fde4e1e46dcc6811b215d2b07ddbb5c5ada22a7ce4dd0688'}, '/opt/analyst-ai/backend/model_json_limits.py': {'bytes': 2324, 'sha256': '2cd9d1f126965ee947b25ee0a5fb82ec5e43b018c5040cd6871b76ca9af7a1ae'}, '/opt/analyst-ai/backend/monitoring_access.py': {'bytes': 1772, 'sha256': '9c6156d1452db85c8adad877e8d9ffe336f499cb44752174e9761a01881fa6cc'}, '/opt/analyst-ai/backend/owner_access.py': {'bytes': 6178, 'sha256': '5bd31e342cea7dbbf1814874a8702140d5669534cd2948c33982b319beee78d3'}, '/opt/analyst-ai/backend/owner_app.py': {'bytes': 5798, 'sha256': '09dda073a447e12f742e4540945e1695be14ce943cf9471189cf4ca80c3d729b'}, '/opt/analyst-ai/backend/portfolio_details.py': {'bytes': 29229, 'sha256': 'd677d2d74f1761b53c507ae716da29d7312f7c526e99a873686008e6ba986a57'}, '/opt/analyst-ai/backend/portfolio_research.py': {'bytes': 20571, 'sha256': '6f657312995316d157424319e75ed876c9d567f52e7a0d267fc30266fac87b70'}, '/opt/analyst-ai/backend/portfolio_risk.py': {'bytes': 23821, 'sha256': 'b796b20085311a6318436c263abe66068dfe8e75e844e6329beec20cc670ce43'}, '/opt/analyst-ai/backend/portfolio_scenarios.py': {'bytes': 7489, 'sha256': '64d2a12e69b5d1dd482d2148d222d1f717b4f04ef6a5218da8357d82faf438ec'}, '/opt/analyst-ai/backend/public_updates_app.py': {'bytes': 1219, 'sha256': '65223e183ab426c2e9fb7619e97aa321f6a9b9c1e4f72392ee8b4fe056edf0d8'}, '/opt/analyst-ai/backend/purchase_policy.py': {'bytes': 12443, 'sha256': 'b4d80849cc55b014dccc76ec463bbf5b1be8cbf18d048a1373f5c16bfcef29fc'}, '/opt/analyst-ai/backend/release_bytes.py': {'bytes': 1807, 'sha256': '71de304be624aed78b53966c66c863aef41d6c961c92badea1f399cd07785ac5'}, '/opt/analyst-ai/backend/release_contract.py': {'bytes': 5885, 'sha256': 'dd6bcbf3c3802dd47003657ee13c548270b0e992cb210fdb3bc2727572d4d933'}, '/opt/analyst-ai/backend/release_json.py': {'bytes': 4285, 'sha256': '04a760b02105322f41d400cbdd6d44a4519c4e8dcd03ffd53fcd6da5fadf6b97'}, '/opt/analyst-ai/backend/release_lock.py': {'bytes': 1638, 'sha256': '548c06b4d8bcc9323eb5e1d49ef17fe4f8689967c2240fd1710653bcab08ce74'}, '/opt/analyst-ai/backend/release_publication.py': {'bytes': 10167, 'sha256': '9f083c508dbfc1e34721e6379044d2071c6e0752029f739e7280a9c65cb6a914'}, '/opt/analyst-ai/backend/research_clock.py': {'bytes': 3137, 'sha256': '267d22a868657d288c89d286ec9007ebf3d01ce25e486f718c5aabbcdf612d70'}, '/opt/analyst-ai/backend/research_import.py': {'bytes': 7893, 'sha256': '806548c1c80d087c3cefe29f9181678f1257faa29760f02ff60e2f57b8e34e4f'}, '/opt/analyst-ai/backend/research_profile_cache.py': {'bytes': 554, 'sha256': '20cb8cd5533dd63ae414ea383dfd1221476762e583e21a67b39602cf5bca3d23'}, '/opt/analyst-ai/backend/research_snapshot.py': {'bytes': 3527, 'sha256': '6971a39d7ba336d3f57b9ec166f61b1687669bc7ec10e982f2473e520da82252'}, '/opt/analyst-ai/backend/research_store.py': {'bytes': 9508, 'sha256': '703b1a251bf3bbae73b8b82bf7647d19a45f3eb0951887bb9822adcc59d5b874'}, '/opt/analyst-ai/backend/risk_math.py': {'bytes': 13842, 'sha256': 'f2492cbbbb7750099b74c5a0564a497d21fef5ffe413971690fe62fb2d049c5c'}, '/opt/analyst-ai/backend/risk_preview.py': {'bytes': 11526, 'sha256': '295a41d0495440366c4cef2aa5f89c6bde5a138e63f269ad7b2b1e050927f82c'}, '/opt/analyst-ai/backend/telegram_browser_app.py': {'bytes': 16927, 'sha256': '5a1ef0f644948cad8d38b4537b9b5c938582fea79955c143453c797b67c46793'}, '/opt/analyst-ai/backend/telegram_oidc.py': {'bytes': 5217, 'sha256': '3d7e64b50811b4b1ff70ec2512f1895f493de77932814976e87e0e509322b3a8'}, '/opt/analyst-ai/backend/timeweb_ai.py': {'bytes': 9066, 'sha256': 'e473a8cddb469b3f5b0a4290fb003d94e03ebb8e960de914406e84e24f7c59a3'}, '/opt/analyst-ai/backend/tinvest_portfolio.py': {'bytes': 16296, 'sha256': '6213499c73fb69b76ddd09a50f4f3a3eb4ac95e42965416d907b201b0711f754'}, '/opt/analyst-ai/backend/volume.py': {'bytes': 630, 'sha256': '2efb14fb95452af54a91899f9b7d3b8dcef694026493eb1061e34e7906e79741'}, '/opt/analyst-ai/backend/volume_analysis.py': {'bytes': 7324, 'sha256': '398c8955a399b7c55eda1939f6cfc5f2c2a137f2a844351f8a8c0cb1931e63cc'}, '/opt/analyst-ai/backend/volume_catalogue.py': {'bytes': 5085, 'sha256': 'f205f57a01804ef79d67e838db832ec62f5cf0353fafff6ed7fb43c0e1aa6e1b'}, '/opt/analyst-ai/backend/volume_chat.py': {'bytes': 44737, 'sha256': '0d258ed870086bbf47ac6747c62484b265a6784bf307f740262acf2d30591c66'}, '/opt/analyst-ai/backend/volume_contract.py': {'bytes': 8050, 'sha256': 'e00250093544aec09f78d86afa597db7aaec690921fc6c90dad6ce01f26a2a41'}, '/opt/analyst-ai/backend/volume_credit.py': {'bytes': 4722, 'sha256': '13a868cf49a848849d68b7f79ee607d7f29318d1fd97ba5c8e35495582cdea41'}, '/opt/analyst-ai/backend/volume_devices.py': {'bytes': 3348, 'sha256': '68440c1b92d81d72d4e01dc16731fa76f4637647e221cb846e0ba67fe08d10dd'}, '/opt/analyst-ai/backend/volume_impact.py': {'bytes': 11925, 'sha256': '38d91ef35eb5e1c850fe64d5ea32c4f9cdd7a501137d0cb922af9a51d4a51d82'}, '/opt/analyst-ai/backend/volume_jobs.py': {'bytes': 18344, 'sha256': 'c18cb703f669ebfc431e8d20292f85851347cfd02c7ae451cea2c911a62e89c6'}, '/opt/analyst-ai/backend/volume_live.py': {'bytes': 8495, 'sha256': 'be782c7cb5c078edbd9693a72909c3b0b455fb73ebe066516f21fe352c9b8b2a'}, '/opt/analyst-ai/backend/volume_market.py': {'bytes': 32918, 'sha256': '6b5883183634b4e23ed15413462bb7fd908c44092ded8bae7ebfc7f00c4b47ce'}, '/opt/analyst-ai/backend/volume_monitor.py': {'bytes': 14437, 'sha256': 'de762346ad2e504c7c9b28f2e97610241c6637b34cdd411ae4df21a5b5cbde6c'}, '/opt/analyst-ai/backend/volume_news.py': {'bytes': 6801, 'sha256': '355d506a59d43089ba4dc4326a3a3fbd6bb009180afecc4be67318b25e01bc57'}, '/opt/analyst-ai/backend/volume_notifications.py': {'bytes': 16328, 'sha256': '74752d772493b173cd33c0cdf207f9d52f2d30c55ffdc78bedd3e68994e9885d'}, '/opt/analyst-ai/backend/volume_plans.py': {'bytes': 16128, 'sha256': '54bd52e549ae5fac4af52a01f0d4515710042383a34207e22f3d591a106ec88e'}, '/opt/analyst-ai/backend/volume_purchases.py': {'bytes': 14574, 'sha256': '21c5db4e53222f8b813e7da22115338f0c8c00dc4149ec0ac0677037cb2aaabe'}, '/opt/analyst-ai/backend/volume_state.py': {'bytes': 40205, 'sha256': '72db61c3c4ecb2ccb10ed68962758dd3121e9e8e5fcc36bc7a2e9b9d1c746d49'}, '/opt/analyst-ai/backend/volume_workspace.py': {'bytes': 38845, 'sha256': '1b5e898823fa0dcdacf978fdd6023da4c9fb7c5ec5057513c277ef55263826a3'}, '/opt/analyst-ai/backend/portfolio_mandate.py': None, '/opt/analyst-ai-updates/backend/public_updates_app.py': {'bytes': 1219, 'sha256': '65223e183ab426c2e9fb7619e97aa321f6a9b9c1e4f72392ee8b4fe056edf0d8'}}, 'units': {'/etc/systemd/system/analyst-ai-owner.service': {'bytes': 923, 'sha256': '7df9096fbc578716208077355fa8ac4cbc5c1480844e83910bfa7a0b40c06ed0'}, '/etc/systemd/system/analyst-ai-updates.service': {'bytes': 893, 'sha256': '98a5a053ccdbb37938b7cac9bcba937da09cdcd828f913ec2750e01d0bc95cc9'}}}
PUBLIC_HOST = 'analyst-ai-2941515.twc1.net'
SERVICES = ('analyst-ai-owner.service', 'analyst-ai-updates.service')
WORKDIRS = frozenset(('/opt/analyst-ai', '/opt/analyst-ai/backend', '/opt/analyst-ai-updates'))
MODULES = frozenset(('owner_app:create_app', 'backend.owner_app:create_app',
                    'app:app', 'backend.app:app', 'telegram_browser_app:app',
                    'backend.telegram_browser_app:app', 'backend.public_updates_app:create_app',
                    'public_updates_app:create_app'))
EXECUTABLES = frozenset(root + '/venv/bin/' + name
                       for root in ('/opt/analyst-ai', '/opt/analyst-ai-updates')
                       for name in ('python', 'python3', 'uvicorn'))
UPSTREAMS = frozenset(('127.0.0.1:8080', '127.0.0.1:8081', '127.0.0.1:8765',
                       'localhost:8080', 'localhost:8081', 'localhost:8765'))
PATHS = frozenset(('/', '/*', '/health', '/client/*', '/client/update-policy',
                   '/client/apk/*', '/client/ready', '/auth/*', '/auth/telegram/*',
                   '/auth/telegram/start', '/auth/telegram/callback', '/auth/telegram/complete',
                   '/api/auth/social/telegram/callback', '/auth/telegram/owner-enrollment/callback',
                   '/releases/*', '/releases/help.html', '/help', '/help.html', '/update-help.html'))
LISTENERS = frozenset((':80', ':443', '0.0.0.0:80', '0.0.0.0:443', '[::]:80', '[::]:443',
                       '127.0.0.1:80', '127.0.0.1:443'))
PROPERTIES = ('ExecStart', 'WorkingDirectory', 'FragmentPath', 'DropInPaths',
              'LoadState', 'ActiveState', 'NeedDaemonReload')

class ObservationError(RuntimeError):
    pass


def need(value, code):
    if not value:
        raise ObservationError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(raw):
    return {'bytes': len(raw), 'sha256': digest(raw)}


def stable(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def trusted_read(path, maximum):
    need(path.is_absolute() and path == Path(PurePosixPath(path).as_posix()), 'noncanonical_fixed_path')
    for parent in reversed(path.parents):
        info = parent.lstat()
        need(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
             and info.st_uid == 0 and not info.st_mode & 0o022, 'untrusted_parent')
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_uid == 0 and before.st_nlink == 1
         and not before.st_mode & 0o022 and 0 < before.st_size <= maximum, 'untrusted_or_oversized_file')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        need(stable(os.fstat(stream.fileno())) == stable(before), 'file_changed_before_read')
        raw = stream.read(maximum + 1)
        need(len(raw) == before.st_size and len(raw) <= maximum
             and stable(os.fstat(stream.fileno())) == stable(before) == stable(path.lstat()),
             'file_changed_during_read')
    return raw


def observed_file(path, maximum):
    try:
        raw = trusted_read(path, maximum)
        return {'status': 'observed', **identity(raw)}, raw
    except FileNotFoundError:
        return {'status': 'absent'}, None
    except (ObservationError, OSError, ValueError):
        return {'status': 'bounded_read_unavailable'}, None


def unique(pairs):
    value = {}
    for key, item in pairs:
        need(key not in value, 'duplicate_json_key')
        value[key] = item
    return value


def active_caddy():
    connection = http.client.HTTPConnection('127.0.0.1', 2019, timeout=5)
    try:
        connection.request('GET', '/config/', headers={'Accept': 'application/json'})
        response = connection.getresponse()
        raw = response.read(2 * 1024**2 + 1)
        need(response.status == 200 and 0 < len(raw) <= 2 * 1024**2, 'active_caddy_unavailable')
        value = json.loads(raw, object_pairs_hook=unique)
        need(type(value) is dict and type(value.get('apps', {}).get('http', {}).get('servers')) is dict,
             'active_caddy_schema_unavailable')
        return {'status': 'observed', **identity(raw)}, value
    except (ObservationError, OSError, ValueError, http.client.HTTPException):
        return {'status': 'bounded_active_configuration_unavailable'}, None
    finally:
        connection.close()



def bounded_systemctl(name):
    need(name in SERVICES, 'unexpected_service')
    command = ['systemctl', 'show', name, '--no-pager', *('--property=' + key for key in PROPERTIES)]
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, close_fds=True)
    raw = bytearray()
    deadline = time.monotonic() + 6
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                need(remaining > 0 and selector.select(remaining), 'systemctl_observation_timeout')
                chunk = os.read(process.stdout.fileno(), min(4096, 65537 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
                need(len(raw) <= 65536, 'systemctl_observation_exceeds_bound')
        need(process.wait(timeout=max(0.1, deadline - time.monotonic())) == 0, 'systemctl_observation_failed')
    finally:
        if process.poll() is None:
            process.kill()  # Only this observer's systemctl show process, never a service.
        process.wait(timeout=2)
        process.stdout.close()
    lines = bytes(raw).decode('utf-8').splitlines()
    values = {}
    for line in lines:
        key, separator, value = line.partition('=')
        need(separator and key in PROPERTIES and key not in values, 'unexpected_systemctl_schema')
        values[key] = value
    need(set(values) == set(PROPERTIES), 'incomplete_systemctl_schema')
    return values


def invocation(value, working_directory, service):
    """Return only finite, recognized argv fields; never echo an unknown argument."""
    result = {'status': 'invocation_not_understood', 'owner_factory_binding_verified': False,
              'public_update_factory_binding_verified': False, 'source_path': None}
    # systemctl show emits structured ExecCommand entries. Multiple commands,
    # escaped values and unrecognized options cannot become a verified binding.
    match = re.fullmatch(r'\{ path=([^;\r\n]+) ; argv\[\]=([^\r\n]+?) ; ignore_errors=(?:yes|no) ; [^\r\n]* \}', value)
    if match is None or value.count('{ path=') != 1:
        return result
    executable, arguments = match.groups()
    if executable not in EXECUTABLES or any(c in arguments for c in ('\\', '\n', '\r', '{', '}')):
        return result
    try:
        argv = shlex.split(arguments, posix=True)
    except ValueError:
        return result
    if not 1 <= len(argv) <= 40 or argv[0] != executable:
        return result
    result.update(executable=executable, argument_count=len(argv))
    tail = argv[1:]
    if executable.rsplit('/', 1)[-1] in {'python', 'python3'}:
        while tail and tail[0] in {'-B', '-u'}:
            tail = tail[1:]
        if tail[:2] != ['-m', 'uvicorn']:
            return result
        tail = tail[2:]
    if not tail or tail[0] not in MODULES:
        return result
    module, tail = tail[0], tail[1:]
    result['module'] = module
    options = {}
    flags = {'--factory', '--no-access-log', '--access-log', '--no-server-header',
             '--server-header', '--proxy-headers', '--no-proxy-headers'}
    finite = {'--host': {'127.0.0.1', 'localhost'}, '--port': {'8080', '8081'},
              '--workers': {'1'}, '--lifespan': {'on', 'auto', 'off'},
              '--log-level': {'critical', 'error', 'warning', 'info', 'debug', 'trace'},
              '--app-dir': WORKDIRS, '--forwarded-allow-ips': {'127.0.0.1'}}
    while tail:
        token, tail = tail[0], tail[1:]
        if token in flags and token not in options:
            options[token] = True
            continue
        if '=' in token:
            option, item = token.split('=', 1)
        elif token in finite and tail:
            option, item, tail = token, tail[0], tail[1:]
        else:
            result['unrecognized_or_duplicate_argument'] = True
            return result
        if option not in finite or option in options or item not in finite[option]:
            result['unrecognized_or_duplicate_argument'] = True
            return result
        options[option] = item
    if any(left in options and right in options for left, right in (
            ('--access-log', '--no-access-log'), ('--proxy-headers', '--no-proxy-headers'),
            ('--server-header', '--no-server-header'))):
        result['unrecognized_or_duplicate_argument'] = True
        return result
    result.update(status='allowlisted_invocation_observed', options=options)
    effective_directory = options.get('--app-dir', working_directory)
    bound = options.get('--factory') is True and options.get('--host') == '127.0.0.1' \
        and options.get('--workers') == '1' and options.get('--lifespan', 'auto') != 'off'
    owner_source = ((module == 'owner_app:create_app' and effective_directory == '/opt/analyst-ai/backend')
                    or (module == 'backend.owner_app:create_app' and effective_directory == '/opt/analyst-ai'))
    update_source = module == 'backend.public_updates_app:create_app' and effective_directory == '/opt/analyst-ai-updates'
    if service == SERVICES[0] and bound and owner_source and options.get('--port') == '8080':
        result.update(owner_factory_binding_verified=True, source_path='/opt/analyst-ai/backend/owner_app.py')
    if service == SERVICES[1] and bound and update_source and options.get('--port') == '8081':
        result.update(public_update_factory_binding_verified=True,
                      source_path='/opt/analyst-ai-updates/backend/public_updates_app.py')
    return result


def service_observation(name):
    try:
        values = bounded_systemctl(name)
        working = values['WorkingDirectory'] if values['WorkingDirectory'] in WORKDIRS else None
        fragment = '/etc/systemd/system/' + name
        result = {
            'status': 'observed', 'working_directory': working,
            'working_directory_allowlisted': working is not None,
            'expected_fragment_path': values['FragmentPath'] == fragment,
            'effective_dropins_present': bool(values['DropInPaths']),
            'load_state': values['LoadState'] if values['LoadState'] in {'loaded', 'not-found', 'error', 'masked'} else 'unknown',
            'active_state': values['ActiveState'] if values['ActiveState'] in {'active', 'inactive', 'failed', 'activating', 'deactivating'} else 'unknown',
            'need_daemon_reload': values['NeedDaemonReload'] if values['NeedDaemonReload'] in {'yes', 'no'} else 'unknown',
            'invocation': invocation(values['ExecStart'], working, name),
        }
        metadata, _ = observed_file(Path(fragment), 128 * 1024)
        result['unit_file_identity'] = metadata
        result['matches_prior_unit_identity'] = {k: metadata.get(k) for k in ('bytes', 'sha256')} == EXPECTED['units'][fragment]
        return result
    except (ObservationError, OSError, ValueError, subprocess.TimeoutExpired):
        return {'status': 'bounded_effective_service_observation_unavailable'}


def allowlisted_list(value, allowed):
    need(type(value) is list and len(value) <= 64 and all(type(item) is str for item in value), 'invalid_route_list')
    return {'values': [item for item in value if item in allowed], 'unrecognized_count': sum(item not in allowed for item in value)}


def sanitized_routes(config):
    """Preserve route/handler ordering and matcher nesting without exposing values.

    This is a review artifact, not an executable Caddy evaluator. Omitted fields
    are counted explicitly; even a familiar proxy target is not deployment proof.
    """
    servers = config['apps']['http']['servers']
    need(type(servers) is dict and 0 < len(servers) <= 8, 'unexpected_server_count')
    visited = 0
    counters = {'file_server': 0, 'inline_html': 0, 'reverse_proxy': 0, 'omitted_fields': 0}
    groups = {}

    def guard(depth):
        nonlocal visited
        visited += 1
        need(visited <= 512 and depth <= 24, 'route_observation_exceeds_bound')

    def matcher(value):
        need(type(value) is dict, 'invalid_matcher')
        result = {}
        for key, allowed in (('host', {PUBLIC_HOST}), ('path', PATHS),
                             ('method', {'GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'}),
                             ('protocol', {'http', 'https', 'grpc'})):
            if key in value:
                result[key] = allowlisted_list(value[key], allowed)
        result['unrecognized_matcher_fields'] = len(set(value) - set(result))
        counters['omitted_fields'] += result['unrecognized_matcher_fields']
        return result

    def handler(value, depth):
        guard(depth)
        need(type(value) is dict, 'invalid_handler')
        kind = value.get('handler')
        allowed_kinds = {'subroute', 'reverse_proxy', 'static_response', 'file_server', 'vars', 'rewrite', 'headers', 'encode'}
        result = {'handler': kind if kind in allowed_kinds else 'unrecognized'}
        used = {'handler'}
        if kind == 'subroute':
            result['routes'] = routes(value.get('routes', []), depth + 1)
            used.add('routes')
        elif kind == 'reverse_proxy':
            counters['reverse_proxy'] += 1
            upstreams = value.get('upstreams', [])
            need(type(upstreams) is list and len(upstreams) <= 16, 'invalid_upstreams')
            result['upstreams'] = []
            for upstream in upstreams:
                need(type(upstream) is dict, 'invalid_upstream')
                result['upstreams'].append({'dial': upstream.get('dial') if upstream.get('dial') in UPSTREAMS else None,
                                            'unrecognized_fields': len(set(upstream) - {'dial'})})
            used.add('upstreams')
        elif kind == 'file_server':
            counters['file_server'] += 1
        elif kind == 'static_response':
            code = value.get('status_code')
            result['status_code'] = code if type(code) is int and 100 <= code <= 599 else None
            body = value.get('body', '')
            result['html_body_present'] = type(body) is str and bool(re.search(r'<(?:!doctype|html|body)\b', body, re.I))
            counters['inline_html'] += int(result['html_body_present'])
            used.update(('status_code', 'body'))
        result['omitted_field_count'] = len(set(value) - used)
        counters['omitted_fields'] += result['omitted_field_count']
        return result

    def routes(values, depth):
        need(type(values) is list and len(values) <= 64, 'invalid_routes')
        result = []
        for index, value in enumerate(values):
            guard(depth)
            need(type(value) is dict, 'invalid_route')
            row = {'index': index}
            if 'match' in value:
                need(type(value['match']) is list and len(value['match']) <= 32, 'invalid_route_matchers')
                row['match_any'] = [matcher(item) for item in value['match']]
            if 'group' in value:
                group = value['group']
                need(type(group) is str and len(group) <= 128, 'invalid_route_group')
                row['group_index'] = groups.setdefault(group, len(groups))
            if 'terminal' in value:
                need(type(value['terminal']) is bool, 'invalid_route_terminal')
                row['terminal'] = value['terminal']
            handlers = value.get('handle', [])
            need(type(handlers) is list and len(handlers) <= 64, 'invalid_route_handlers')
            row['handle'] = [handler(item, depth + 1) for item in handlers]
            row['omitted_field_count'] = len(set(value) - {'match', 'group', 'terminal', 'handle'})
            counters['omitted_fields'] += row['omitted_field_count']
            result.append(row)
        return result

    result = []
    for index, value in enumerate(servers.values()):
        need(type(value) is dict, 'invalid_http_server')
        result.append({'server_index': index, 'listen': allowlisted_list(value.get('listen', []), LISTENERS),
                       'routes': routes(value.get('routes', []), 0),
                       'other_server_field_count': len(set(value) - {'listen', 'routes'})})
    return {'status': 'allowlisted_ordered_route_tree_observed', 'servers': result, 'counts': counters,
            'route_evaluator_executed': False, 'deployment_binding_verified': False,
            'help_route_created': False, 'requires_manual_route_review': True}


def main():
    need(sys.platform == 'linux' and os.geteuid() == 0, 'wrong_observer_platform')
    sources = {}
    for name, expected in EXPECTED['sources'].items():
        path = Path(name)
        try:
            path.lstat()
        except FileNotFoundError:
            sources[name] = {'status': 'absent', 'matches_reference47': expected is None}
            continue
        metadata, raw = observed_file(path, 2 * 1024**2)
        if raw is not None:
            metadata['matches_reference47'] = identity(raw) == expected
        sources[name] = metadata
    services = {name: service_observation(name) for name in SERVICES}
    caddy, _ = active_caddy()
    config, _ = observed_file(Path('/etc/caddy/Caddyfile'), 128 * 1024)
    connection = http.client.HTTPConnection('127.0.0.1', 8080, timeout=5)
    try:
        connection.request('GET', '/health')
        response = connection.getresponse()
        body = response.read(1025)
        need(response.status == 200 and len(body) <= 1024 and json.loads(body) == {'status': 'ok'}, 'owner_health_failed')
    finally:
        connection.close()
    result = {'schema': 1, 'kind': 'portfolio_mandate48_runtime_readonly',
        'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'runtime_server_id': 9417611, 'public_host': PUBLIC_HOST,
        'sources': sources, 'services': services, 'active_caddy_configuration': caddy,
        'caddy_file': config, 'local_health_status': 200,
        'application_imported': False, 'application_or_tests_executed': False,
        'environment_file_or_database_read': False, 'source_or_configuration_text_exported': False,
        'runtime_files_written': False, 'services_restarted': False,
        'private_app_routes_requested': False, 'model_or_broker_calls': False}
    raw = (json.dumps(result, sort_keys=True) + '\n').encode()
    need(len(raw) <= 128 * 1024, 'observation_exceeds_bound')
    sys.stdout.buffer.write(raw)


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        code = str(error) if isinstance(error, ObservationError) else type(error).__name__
        if re.fullmatch(r'[A-Za-z0-9_]{1,100}', code) is None:
            code = 'mandate_runtime_observation_failed'
        print('MANDATE48_OBSERVATION_FAILED=' + code, file=sys.stderr, flush=True)
        raise SystemExit(1) from None
