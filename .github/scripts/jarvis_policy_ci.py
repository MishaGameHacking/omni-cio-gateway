"""Synthetic Jarvis integration tests in a disposable Lenovo virtual environment."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

TESTS = [
    'backend/tests/test_agent_runtime_policy.py',
    'backend/tests/test_agent_task_client.py',
    'backend/tests/test_agent_analysis_runtime.py',
    'backend/tests/test_autonomous_ai.py',
    'backend/tests/test_ai_policy.py',
    'backend/tests/test_ai_accounting_audit.py',
    'backend/tests/test_ai_jobs_schema_atomic.py',
    'backend/tests/test_ai_budget_schema_atomic.py',
]


def main():
    if sys.platform != 'win32' or os.environ.get('COMPUTERNAME') != 'LAPTOP-NPSGA016':
        raise RuntimeError('owner_lenovo_required')
    root = Path(__file__).resolve().parents[2]
    runner_temp = Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
    allowed = {'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATH', 'PATHEXT', 'TEMP', 'TMP',
               'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA', 'PROGRAMFILES',
               'PROGRAMFILES(X86)', 'COMMONPROGRAMFILES', 'SYSTEMDRIVE'}
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1',
               PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PIP_CONFIG_FILE=os.devnull,
               PIP_DISABLE_PIP_VERSION_CHECK='1', ANALYSIS_SCHEDULER_ENABLED='false',
               AI_EXTERNAL_PROCESSING_APPROVED='false')
    with tempfile.TemporaryDirectory(prefix='jarvis-ci-', dir=runner_temp) as temp:
        venv = Path(temp) / 'venv'
        env['DATABASE_PATH'] = str(Path(temp) / 'unused-test-only.sqlite3')
        def run(args, timeout=180):
            subprocess.run(args, cwd=root, env=env, stdin=subprocess.DEVNULL,
                           timeout=timeout, check=True)
        run([sys.executable, '-I', '-m', 'venv', str(venv)])
        python = str(venv / 'Scripts' / 'python.exe')
        run([python, '-I', '-m', 'pip', '--isolated', '--require-virtualenv', 'install',
             '--no-input', '--no-cache-dir', '--only-binary=:all:',
             '--index-url', 'https://pypi.org/simple', '-r', 'backend/requirements-dev.txt'])
        run([python, '-I', '-m', 'pip', 'check'])
        code = ('import pathlib,sys,pytest; sys.path.insert(0,str(pathlib.Path.cwd())); '
                'raise SystemExit(pytest.main(' + repr(TESTS + ['-q', '-p', 'no:cacheprovider']) + '))')
        run([python, '-I', '-c', code])
        print('JARVIS_TARGETED_TESTS=passed; disposable test environment removed on exit', flush=True)


if __name__ == '__main__':
    main()
