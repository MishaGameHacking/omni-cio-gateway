"""Linux half of the credential-free, network-blocked administration test job."""
import json
import os
from pathlib import Path
import pwd
import sys
import unittest
import urllib.request  # Initialize SSL classes before replacing socket.socket.
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['tools/inspect_owner55_ai.py', 'tools/provision_owner55_ai.py',
           'tools/owner_ai_private_transport.py', 'deploy/stage_owner55_ai.py',
           'tools/check_owner55_ai_tools.py', 'tools/run_owner55_ai_tests.py',
           'tools/activate_owner55_ai.py', 'deploy/activate_owner55_ai.py',
           'tools/launch_owner55_ai_wsl.py', 'tools/owner55_ai_guest.py',
           'tools/owner_ai_admin_transport.py', 'tools/admin_owner55_ai.py',
           'tools/check_owner55_ai_admin_tools.py', 'tools/run_owner55_ai_admin_tests.py']
PATTERNS = ['test_inspect_owner55_ai.py', 'test_provision_owner55_ai.py',
            'test_owner_ai_private_transport.py', 'test_activate_owner55_ai.py',
            'test_owner55_ai_launcher.py', 'test_owner_ai_admin_transport.py',
            'test_admin_owner55_ai.py']


def main():
    if sys.platform != 'linux' or 'microsoft' not in Path('/proc/sys/kernel/osrelease').read_text().lower():
        raise RuntimeError('existing_owner_wsl_required')
    if pwd.getpwuid(os.getuid()).pw_name != 'analyst-ci':
        raise RuntimeError('owner_wsl_test_user_required')
    if any(os.environ.get(name) for name in ('TIMEWEB_CLOUD_TOKEN', 'TIMEWEB_AI_TOKEN', 'GITHUB_TOKEN')):
        raise RuntimeError('test_job_must_not_receive_credentials')
    os.chdir(ROOT)
    for relative in SOURCES:
        compile((ROOT / relative).read_text(encoding='utf-8'), relative, 'exec')
    # Mocked adapters must be the only path available during these tests.
    # A forgotten patch cannot turn this job into a provider or SSH call.
    with mock.patch('socket.socket', side_effect=AssertionError('network_forbidden_in_synthetic_tests')):
        suite = unittest.TestSuite()
        for pattern in PATTERNS:
            suite.addTests(unittest.defaultTestLoader.discover(str(ROOT / 'tools/tests'), pattern=pattern))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    print(json.dumps({'status': 'passed', 'tests_run': result.testsRun,
        'network_permitted': False, 'synthetic_tests_only': True}), flush=True)


if __name__ == '__main__':
    main()
