"""Install an owner-supplied one-time setup key through protected administration.

With no GitHub secret, performs read-only readiness and explains that the owner
must supply a key. A successful rerun verifies the existing service loaded it.
No public default password, generated key artifact, or authentication bypass.
"""
from contextlib import redirect_stdout, redirect_stderr
import json
import os
from pathlib import Path
import re

from admin_owner55_ai import DiscardedOutput
from owner_ai_admin_transport import require_admin_guard, transport_admin

BOOTSTRAP = 'ANALYST_OWNER_BOOTSTRAP_SECRET'
AUTH_SOURCES = {'owner_password.py', 'owner_password_routes.py', 'owner_access.py'}
BOOLEAN_FIELDS = ('password_configured', 'bootstrap_configured', 'configuration_changed',
    'service_restarted', 'bootstrap_loaded', 'key_matches_supplied',
    'preserved_configuration', 'health_verified', 'auth_boundary_verified', 'public_feed_unchanged')
STATUSES = {'waiting_for_secret', 'bootstrap_ready', 'already_configured', 'blocked'}
PHASES = {'source_verification', 'service_metadata', 'owner_status',
          'bootstrap_validation', 'configuration_write', 'restart', 'runtime_verification', 'complete'}


def source_proof(environment):
    value = json.loads(environment['OWNER_BOOTSTRAP_EXPECTED_SOURCES'])
    if not isinstance(value, dict) or set(value) != AUTH_SOURCES or any(
        not isinstance(v, str) or re.fullmatch('[a-f0-9]{64}', v) is None for v in value.values()
    ):
        raise RuntimeError('bootstrap_source_proof_invalid')
    return value


def operation_source():
    root = Path(__file__).resolve().parents[1]
    stage = (root / 'deploy/stage_owner55_ai.py').read_text(encoding='utf-8')
    active = (root / 'deploy/activate_owner55_ai.py').read_text(encoding='utf-8')
    bootstrap = (root / 'deploy/provision_owner55_bootstrap.py').read_text(encoding='utf-8')
    return ('support={"__name__":"owner_staging"}\nexec(compile(' + repr(stage) + ',"staging","exec"),support)\n'
        'active={"__name__":"owner_active","STAGING":support}\nexec(compile(' + repr(active) + ',"activation","exec"),active)\n'
        'exec(compile(' + repr(bootstrap) + ',"owner-bootstrap","exec"),'
        '{"STAGING":support,"ACTIVATION":active,"ENVELOPE":ENVELOPE,"__name__":"__main__"})\n')


def execute(environment, transfer=transport_admin):
    sources = source_proof(environment)
    secret = environment.get(BOOTSTRAP) or None
    if secret is not None and (not isinstance(secret, str) or re.fullmatch('[A-Za-z0-9_-]{32,128}', secret) is None):
        return {'status': 'blocked', 'reason': 'bootstrap_secret_must_be_32_to_128_ascii_letters_digits_dash_underscore'}
    contract = {field: bool for field in BOOLEAN_FIELDS}
    contract.update(status=STATUSES, phase=PHASES, server_id=int,
                    minimum_bootstrap_length=int, minimum_password_length=int)
    return transfer(operation_source(), {'source_sha256': sources}, secret, contract)


def summary(receipt):
    status = receipt.get('status')
    if status == 'bootstrap_ready':
        return ('# Ключ готов для первого входа\n\n'
            'Откройте Analyst AI. Введите новый личный пароль (не менее 10 символов), '
            'повторите его и в поле «Одноразовый ключ настройки» вставьте то же значение, '
            'которое вы сохранили в GitHub Secret `ANALYST_OWNER_BOOTSTRAP_SECRET`. '
            'Нажмите «Сохранить пароль и войти». Сам ключ здесь не отображается.\n')
    if status == 'already_configured':
        return ('# Личный пароль уже создан\n\n'
            'Откройте Analyst AI и войдите со своим сохранённым паролем. '
            'Одноразовый ключ больше не используется. Этот запуск пароль не менял.\n')
    if status == 'waiting_for_secret':
        return ('# Ожидается ваш одноразовый ключ\n\n'
            'Добавьте repository Actions secret с именем `ANALYST_OWNER_BOOTSTRAP_SECRET`. '
            'Значение: ваша новая случайная строка из 32–128 латинских букв, цифр, `-` и `_`. '
            'Сохраните значение у себя, затем здесь нажмите **Re-run all jobs**. '
            'Этот запуск только проверил готовность сервера; ключ пока не установлен.\n')
    return ('# Подготовка входа не подтверждена\n\n'
            'Не создавайте другой аккаунт и не удаляйте приложение. '
            'Сообщите статус запуска для проверки; пароль и ключ в чат присылать не нужно.\n')


def main():
    receipt = {'status': 'blocked', 'reason': 'private_bootstrap_preparation_failed'}
    try:
        with redirect_stdout(DiscardedOutput()), redirect_stderr(DiscardedOutput()):
            require_admin_guard()
            receipt = execute(os.environ)
    except BaseException:
        pass
    print('OWNER_ENTRY_SETUP=' + json.dumps(receipt, sort_keys=True), flush=True)
    destination = os.environ.get('GITHUB_STEP_SUMMARY')
    if destination:
        with Path(destination).open('a', encoding='utf-8') as output:
            output.write(summary(receipt))
    if receipt['status'] == 'waiting_for_secret':
        print('::notice::Add ANALYST_OWNER_BOOTSTRAP_SECRET in repository Actions secrets, then Re-run all jobs.', flush=True)
    if receipt['status'] == 'blocked':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
