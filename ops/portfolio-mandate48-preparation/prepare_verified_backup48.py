"""Prepare Git backup entries from original successful laptop evidence; never run app code."""
from pathlib import Path
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET

CONTEXT = Path(__file__).resolve().parent.parent

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    candidate, evidence, output = (CONTEXT / name for name in (args.candidate, args.evidence, args.output))
    for path in (candidate, evidence):
        assert path.parent == CONTEXT and path.resolve(strict=True) == path and path.is_dir()
    assert output.parent == CONTEXT and not output.exists()
    load = lambda path: json.loads(path.read_bytes())
    prepared = load(candidate / 'manifest-summary.json')
    raw_review = (candidate / 'reviewed-files.json').read_bytes()
    assert digest(raw_review) == prepared['reviewed_files_sha256']
    review = json.loads(raw_review)
    report = load(evidence / 'windows-development.json')
    controller = load(evidence / 'controller.json')
    inventory = load(evidence / 'source-final.json')
    exported = load(evidence / 'export-receipt.json')
    assert report['status'] == exported['status'] == 'passed_check_and_build_only'
    assert report['host'] == 'LAPTOP-NPSGA016' and report['origin'] == 'Windows laptop'
    assert controller['worker_exit_code'] == 0 and controller['owned_processes_after'] == 0
    assert controller['worker_started'] and not controller.get('error') and not controller.get('cleanup_error')
    assert controller['finished_at'] and controller['lease_acquired_at']
    assert report['certificate_sha256'] == 'bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1'
    assert report['source_sha256'] == report['source_sha256_after'] == inventory['source_sha256'] == exported['source_sha256']
    assert report['complete_source_sha256'] == inventory['complete_source_sha256'] == exported['complete_source_sha256']
    assert report['bootstrap_sha256'] == prepared['bootstrap_sha256']
    assert report['patch_manifest_sha256'] == prepared['patch_manifest_sha256']
    assert all(report[phase]['status'] == 'passed' for phase in ('check', 'build'))
    assert all(step['exit_code'] == 0 for step in report['steps'])
    assert {'host-tests', 'tools-tests', 'node-tests', 'backend-tests', 'gradle', 'apk-verification'} <= {s['label'] for s in report['steps']}
    assert report['runtime']['status'] == 'not_run' and report['phone_verified'] is False
    actual_patches = {r['path']: r for r in report['patch_files']}
    assert set(actual_patches) == {r['path'] for r in review['files']}
    code, complete = hashlib.sha256(), hashlib.sha256()
    for name, row in sorted(inventory['files'].items(), key=lambda item: item[0].encode()):
        entry = name.encode() + b'\0' + row['sha256'].encode() + b'\0'
        complete.update(entry)
        if name not in ('AGENTS.md', 'README.md') and not name.startswith('docs/'):
            code.update(entry)
    assert code.hexdigest() == inventory['source_sha256'] and complete.hexdigest() == inventory['complete_source_sha256']
    entries = []
    for row in review['files']:
        raw = row['content'].encode()
        assert digest(raw) == row['new_sha256'] and len(raw) == row['new_bytes']
        assert inventory['files'][row['path']] == {'bytes': len(raw), 'sha256': digest(raw)}
        patch = actual_patches[row['path']]
        assert patch['old_sha256'] == row['old_sha256'] and patch['new_sha256'] == row['new_sha256']
        entries.append({'path': row['path'], 'mode': '100644', 'type': 'blob', 'content': row['content']})
    suites = [ET.fromstring(path.read_bytes()) for path in evidence.glob('TEST-*.xml')]
    assert suites and all(int(s.get('failures', '-1')) == int(s.get('errors', '-1')) == int(s.get('skipped', '-1')) == 0 for s in suites)
    jvm = sum(int(s.get('tests')) for s in suites)
    run = report['github']['run_id']
    provenance = {'schema': 1, 'kind': 'verified_windows_source_backup_preparation',
        'run_id': run, 'workflow_sha': report['github']['workflow_sha'],
        'source_sha256': inventory['source_sha256'], 'complete_source_sha256': inventory['complete_source_sha256'],
        'source_files': len(entries), 'jvm_tests': jvm, 'jvm_suites': len(suites),
        'native_passed': False, 'apk_published': False, 'server_deployed': False, 'plan_complete': False,
        'original_evidence': {p.name: {'sha256': digest(p.read_bytes()), 'bytes': p.stat().st_size}
            for p in [evidence/'windows-development.json', evidence/'controller.json', evidence/'source-final.json', evidence/'export-receipt.json']}}
    note = f'''# Проверенная сборка профиля48 · 26.10.2026

Windows/WSL run [{run}](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/{run})
прошёл все исходные check/build этапы на LAPTOP-NPSGA016.
Проверены {jvm} JVM-тестов ({len(suites)} suites), без ошибок и пропусков.
Сохранены точные {len(entries)} изменённых Windows-файлов; код SHA256 `{inventory['source_sha256']}`.
Исходный полный архив: `{exported['sha256']}`, {exported['bytes']} bytes.

Это резервная копия проверенной сборки48 /0.14.1-preview. Полная нативная
матрица и установка на физическом телефоне не подтверждены. Владелец разрешил
промежуточное обновление без повторной полной матрицы; прежние отказы сохранены.
Публикация47 уже подтверждена run40396872198:29 921 459bytes,
SHA256 `1f699684618f44f1da4c71f3fa19bbf9125e906ab431865747cf44e0b5ea0602`.
На момент этого build-checkpoint выпуск48 и применение четырёх серверных модулей
ещё требуют собственных фактических receipts; этот документ их не подменяет.

Новый профиль хранится в прежней версионированной стратегии: облигации, акции
или смешанный режим; рублёвый счёт из полученных данных брокера; точные доли,
допустимый убыток, рейтинг, оборот, расходы, пауза и выбор по поступлениям.
Нет автоподстановки инвестиционного профиля. Неполный выбор остаётся зашифрованным
черновиком; полный проходит серверную проверку и сохраняется автоматически.
Числовые настройки используют готовые варианты, точные шаги и процентный слайдер.
Старый клиент не стирает новый профиль; выбранный счёт проверяется повторно
в транзакции сохранения. Подтверждены21 новых серверных сценарий и3 JVM-сценария
точных элементов управления в составе полных исходных наборов.

Это первый рабочий слойN01. Состав, выбранный счёт, нулевая способность к потерям
и более строгий рейтинг учитываются в проверках; полный расчёт положительного
риска, оборота/издержек и перераспределения зависит отN04/N07. Реинвестирование,
торговый исполнитель и реальные поручения не включены. Первая сборка48
40398531747 сохранила реальный отказ: семисимвольный request_id в новом тесте;
исправлен тестовый запрос, а не проверка сервера.232 JVM-теста того прогона прошли,
но его общий результат не объявляется успешным.

N00–N11 целиком не завершены. Следующий функциональный этап — календарь торгов,
отдельные круглосуточные события и приоритеты работN02; затем источникиN03.
N10 требует30 фактических торговых сессий. План не завершён.
'''
    entries.append({'path': f'docs/VERIFIED_MANDATE48_BUILD_{run}.md', 'mode': '100644', 'type': 'blob', 'content': note})
    output.mkdir()
    (output/'provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+'\n')
    encoded = json.dumps(entries, ensure_ascii=False)
    (output/'tree-elements.json').write_text(encoded)
    print(json.dumps({'entries': len(entries), 'characters': len(encoded), 'tree_elements_sha256': digest(encoded.encode()), 'provenance': provenance}))

if __name__ == '__main__':
    main()
