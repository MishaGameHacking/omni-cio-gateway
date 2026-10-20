"""Apply reviewed current-platform edits in an isolated migration checkout only."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
EDITS = {
    '.github/PULL_REQUEST_TEMPLATE.md': [
        ('Текущая платформа: Android 15+, minSdk 35, compile/target 36.', 'Текущая платформа: Android 17+, minSdk 37, compile/target 37.'),
        ('API 35 / API 36: установка, обновление и UI', 'API 37 / 4 KB и 16 KB: установка, обновление и UI'),
        ('Физический Android 15+ / установка через UI updater', 'Физический Android 17+ / установка через UI updater'),
    ],
    '.github/scripts/tests/test_emulator_navigation_config.py': [
        ('system-images;android-35;google_apis_ps16k;x86_64', 'system-images;android-37.0;google_apis_ps16k;x86_64'),
    ],
    '.github/scripts/tests/test_emulator_storage.py': [
        ('system-images;android-35;google_apis_ps16k;x86_64', 'system-images;android-37.0;google_apis_ps16k;x86_64'),
    ],
    '.github/scripts/tests/test_emulator_rotation.py': [
        ('real API35/API36 UI gate', 'real API37 4KB/16KB UI gate'),
    ],
    '.github/scripts/tests/test_spectrum_brand_identity.py': [
        ('для Android 15 и новее', 'для Android 17 и новее'),
    ],
    'app/src/main/java/ru/omnicio/app/ui/profile/ProfileScreen.kt': [
        ('для Android 15 и новее', 'для Android 17 и новее'),
    ],
    'app/src/main/java/ru/omnicio/app/ui/spatial/README.md': [
        ('next API 35/36', 'next API37 4KB/16KB'),
        ('actual API 35/36 devices/emulators, including an Android 15 16KB environment.', 'actual API37 devices/emulators, with independently measured 4KB and 16KB environments.'),
    ],
    'app/src/debug/AndroidManifest.xml': [
        (' android:usesCleartextTraffic="false"', ''),
    ],
    'ci-ui-driver/src/main/AndroidManifest.xml': [
        (' android:usesCleartextTraffic="false"', ''),
    ],
    'app/src/main/res/values/themes.xml': [
        ('        <item name="android:navigationBarColor">@android:color/transparent</item>\n', ''),
    ],
    '.github/scripts/private_apk_review.cjs': [
        ("const crypto = require('node:crypto');", "const crypto = require('node:crypto');\nconst {newestSonarCheck, assertCleanSonar} = require('./require_clean_sonar.cjs');"),
        ("function validateBytes(report, apk) {\n  if (", "function validateBytes(report, apk) {\n  if (report.min_sdk !== 37 || report.target_sdk !== 37) {\n    throw new Error('Private APK requires the exact current Android platform');\n  }\n  if ("),
        ("  const sonar = checks.filter(check => check.name === 'SonarCloud Code Analysis')\n    .sort((a, b) => b.id - a.id)[0];\n  if (sonar?.status !== 'completed' || sonar.conclusion !== 'success') {\n    throw new Error('Exact-head Sonar must pass before retaining a device-test APK');\n  }",
         "  const sonar = newestSonarCheck(checks, head);\n  const annotations = sonar ? await github.paginate(github.rest.checks.listAnnotations,\n    {...context.repo, check_run_id: sonar.id, per_page: 100}) : [];\n  assertCleanSonar(sonar, annotations, head);"),
        ('preview: Android 15+', 'preview: Android 17+'),
        ('на API35/16KB и API36', 'на API37 с измеренными страницами 16KB и 4KB'),
    ],
    '.github/scripts/tests/fixtures/private_apk_review.test.cjs': [
        ("const report = {package:", "const report = {min_sdk: 37, target_sdk: 37, package:"),
        ('  const listForRef = () => {};', '  const listForRef = () => {};\n  const listAnnotations = () => {};'),
        ('checks: {listForRef}', 'checks: {listForRef, listAnnotations}'),
        ("    if (route === listForRef) return [{id: 7, name: 'SonarCloud Code Analysis', status: 'completed', conclusion: options.sonar || 'success'}];",
         "    if (route === listForRef) {\n      const check = {id: 7, head_sha: options.wrongHead ? base : head,\n        name: 'SonarCloud Code Analysis', app: {slug: options.fakeApp ? 'github-actions' : 'sonarqubecloud'},\n        status: 'completed', conclusion: options.sonar || 'success',\n        output: {annotations_count: options.annotation ? 1 : 0,\n          summary: `[${options.newIssues || 0} New issues](https://example.invalid/new)\\n[${options.acceptedIssues || 0} Accepted issues](https://example.invalid/accepted)`}};\n      return options.newerPending ? [check, {...check, id: 9, status: 'in_progress', conclusion: null}] : [check];\n    }\n    if (route === listAnnotations) return options.annotation ? [{annotation_level: 'warning'}] : [];"),
        ('/must pass/);', '/sonar_quality_gate_not_successful|must pass/);'),
    ],
    '.github/scripts/tests/test_private_apk_review.py': [
        ('"# pass 8"', '"# pass 12"'),
    ],
}
PRIVATE_TESTS = r'''
test('old, future-target and malformed platform reports cannot produce a current draft', async () => {
  for (const report of [{min_sdk: 35}, {min_sdk: 36}, {min_sdk: '37'}, {min_sdk: null},
      {target_sdk: 36}, {target_sdk: 38}, {target_sdk: '37'}, {target_sdk: null}]) {
    await run({report}, async f => {
      await assert.rejects(retain(f), /exact current Android platform/);
      assert.deepEqual(f.writes, []);
    });
  }
});
test('a similarly named check from another app or SHA cannot authorize retention', async () => {
  for (const options of [{fakeApp: true}, {wrongHead: true}]) {
    await run(options, async f => {
      await assert.rejects(retain(f), /sonar_exact_head_result_missing/);
      assert.deepEqual(f.writes, []);
    });
  }
});
test('successful gate with annotations or nonzero issue counts remains blocked', async () => {
  for (const options of [{annotation: true}, {newIssues: 1}, {acceptedIssues: 1}]) {
    await run(options, async f => {
      await assert.rejects(retain(f), /sonar_annotations_not_clean_or_incomplete|sonar_summary_zero_issues_not_confirmed/);
      assert.deepEqual(f.writes, []);
    });
  }
});
test('new pending analysis cannot reuse an older successful analysis', async () => {
  await run({newerPending: true}, async f => {
    await assert.rejects(retain(f), /sonar_quality_gate_not_successful/);
    assert.deepEqual(f.writes, []);
  });
});
'''
ANDROID_POLICY = '''## Android

- Действующая минимальная ОС — **Android 17 / API 37**. Новое указание OWNER 19–20.10.2026 отменяет прежнюю поддержку более старых ОС во всём текущем проекте.
- `minSdk = 37`, `compileSdk = 37`, `targetSdk = 37`; app и отдельный test-only driver используют один стандарт. Новые уровни API добавляются только после отдельной проверки.
- Использовать стабильные публичные API и поддерживаемые инструменты. Поддерживаемый API не устарел лишь потому, что появился раньше минимальной ОС; не добавлять обходы для неподдерживаемых версий.
- Edge-to-edge, safeDrawing/IME-insets и настоящий predictive Back обязательны. Не заменять системный жест прямым callback или KEYCODE_BACK.
- Не блокировать ориентацию/размер окна. Проверять поворот, split-screen, большой шрифт, отмену жеста, возобновление и потерю процесса.
- Сохранять Filament/gltfio и нативный доступный текст/ввод; учитывать lifecycle, системное отключение движения и тепловые ограничения.
- Сетевые ключи, аналитика и платные модельные вызовы остаются на сервере. Кадровые callback не запускают сеть/ИИ.
- Обязательная матрица нового APK: API37 x86_64 с фактически измеренными `getconf PAGE_SIZE` 4096 и 16384. Для каждого профиля обязательны отдельные установка, обновление, запуск и полная UI-проверка, связанные с SHA-256 кандидата.
- Старый APK служит только проверенным байтовым источником теста обновления НА поддерживаемой ОС. Исторические протоколы не переименовывать в новые результаты и не использовать для разрешения нового выпуска.
- Основное физическое устройство владельца — Samsung Galaxy S25 Ultra, Android 17 / One UI 9.0. Его проверку не объявлять по эмулятору; идентификаторы телефона/IMEI в репозиторий не переносить.
- До завершения 0.11.0 не обновлять Timeweb, backend, серверный APK и канал. Разрешено сливать только действительно готовые и проверенные ветки. Тестовый APK — отдельный приватный draft после всех проверок, не производственный выпуск.
- Исторические отчёты сохраняются с исходными датами в архиве; они не задают поддержку текущей линии.

'''


def replace_once(text, old, new, name):
    if text.count(old) != 1:
        raise ValueError(f'Changed source fragment: {name}: {old[:90]}')
    return text.replace(old, new, 1)


def main():
    prepared = {}
    for name, edits in EDITS.items():
        text = (ROOT / name).read_text(encoding='utf-8')
        for old, new in edits:
            text = replace_once(text, old, new, name)
        prepared[name] = text
    fixture = '.github/scripts/tests/fixtures/private_apk_review.test.cjs'
    prepared[fixture] += PRIVATE_TESTS
    agents = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
    start, end = agents.index('## Android\n'), agents.index('## Как понимать запросы OWNER\n')
    if start >= end:
        raise ValueError('Android policy boundary changed')
    agents = agents[:start] + ANDROID_POLICY + agents[end:]
    agents = replace_once(agents, '**Сверка 17.10.2026:**', '**Историческая сверка 17.10.2026 (не текущая поддержка):**', 'AGENTS.md')
    agents = replace_once(agents, 'Поддержка Android 15+ обязательна.', 'Историческое требование поддержки ОС заменено текущим разделом Android.', 'AGENTS.md')
    prepared['AGENTS.md'] = agents
    renames = {
        '.github/scripts/tests/test_android16_manifest.py': '.github/scripts/tests/test_android17_manifest.py',
        '.github/scripts/tests/test_android16_live_spectrum.py': '.github/scripts/tests/test_android17_live_spectrum.py',
    }
    for old, new in renames.items():
        if (ROOT / new).exists():
            raise ValueError('Rename destination already exists')
        prepared[new] = (ROOT / old).read_text(encoding='utf-8').replace('Android 16-only', 'Android 17-only').replace('Android16ManifestTests', 'Android17ManifestTests')
    for name, text in prepared.items():
        if name.endswith('.py'):
            compile(text, name, 'exec')
    for name, text in prepared.items():
        with (ROOT / name).open('w', encoding='utf-8', newline='\n') as output:
            output.write(text)
    for old in renames:
        (ROOT / old).unlink()
    paths = sorted(set(prepared) | set(renames))
    (ROOT / '.git/android17-refactor.json').write_text(json.dumps([{'path': name} for name in paths]), encoding='utf-8')
    print('CURRENT_PLATFORM_EDITS=' + json.dumps(paths))


if __name__ == '__main__':
    main()
