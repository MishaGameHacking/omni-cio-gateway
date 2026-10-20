"""Exact-baseline migration in a disposable checkout; never deploys or pushes."""
from __future__ import annotations
import argparse
import ast
import json
from pathlib import Path
import re
import subprocess

BASE = '6c04c78f3453979df336197d744b17b45636f89d'


def replace(text, before, after, count=1):
    actual = text.count(before)
    if actual != count:
        raise ValueError(f'Expected {count} occurrences of {before!r}, found {actual}')
    return text.replace(before, after)


def function(text, name, replacement, owner=None):
    nodes = ast.parse(text).body
    if owner:
        nodes = next(n for n in nodes if isinstance(n, ast.ClassDef) and n.name == owner).body
    found = [n for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(found) != 1:
        raise ValueError(f'Function {owner}.{name} not unique')
    node = found[0]
    lines = text.splitlines(keepends=True)
    start = min([node.lineno, *(d.lineno for d in node.decorator_list)]) - 1
    indent = ' ' * node.col_offset
    body = ''.join(indent + line + '\n' if line else '\n' for line in replacement.strip().splitlines())
    return ''.join(lines[:start]) + body + ''.join(lines[node.end_lineno:])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--templates', type=Path, required=True)
    args = parser.parse_args()
    root, templates = args.source.resolve(strict=True), args.templates.resolve(strict=True)
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if sha != BASE:
        raise ValueError('Migration requires the inspected source baseline')
    changes = {}
    def read(name):
        return changes[name] if name in changes else (root / name).read_text(encoding='utf-8')
    def edit(name, before, after, count=1):
        try:
            changes[name] = replace(read(name), before, after, count)
        except ValueError as error:
            raise ValueError(name + ': ' + str(error)) from error
    def replace_fn(name, target, content, owner=None):
        changes[name] = function(read(name), target, content, owner)

    mapping = {
        'android_platform.py': 'backend/android_platform.py',
        'kernel_page_size.py': '.github/scripts/kernel_page_size.py',
        'android_sdk.py': '.github/scripts/android_sdk.py',
        'emulator_profile.py': '.github/scripts/emulator_profile.py',
        'validate_distribution.py': '.github/scripts/validate_distribution.py',
        'android17_fixtures.py': 'backend/tests/android17_fixtures.py',
        'test_android_platform.py': 'backend/tests/test_android_platform.py',
        'test_kernel_page_size.py': '.github/scripts/tests/test_kernel_page_size.py',
    }
    for source, target in mapping.items():
        changes[target] = (templates / source).read_text(encoding='utf-8')
    for name in ('app/build.gradle.kts', 'ci-ui-driver/build.gradle.kts'):
        edit(name, 'compileSdk = 36', 'compileSdk = 37\n    buildToolsVersion = "37.0.0"')
        edit(name, 'minSdk = 35', 'minSdk = 37')
        edit(name, 'targetSdk = 36', 'targetSdk = 37')
    edit('app/src/main/java/ru/omnicio/app/data/updates/ReleaseDescriptor.kt',
         'minSdk in 33..100', 'minSdk in 37..100')
    edit('app/src/main/java/ru/omnicio/app/ui/profile/ProfileScreen.kt',
         'Android 15 и новее', 'Android 17 и новее')
    edit('backend/client_updates.py', "_integer(raw['min_sdk'], 33, 100)", "_integer(raw['min_sdk'], 37, 100)")

    name = 'backend/installation_evidence.py'
    prefix = read(name).split('def _one_emulator(')[0].replace('Android 15/16', 'Android 17')
    changes[name] = prefix + (templates / 'installation_tail.py').read_text(encoding='utf-8')
    name = 'backend/release_publication.py'
    replace_fn(name, '_require_supported_installation', '''
def _require_supported_installation(report: dict, *, sha256: str) -> dict:
    tested = report.get('installation_evidence')
    if not isinstance(tested, dict) or tested.get('apk_sha256') != sha256:
        raise ReleaseUnavailable('installation_evidence_missing')
    for case in ('37-16k', '37-4k'):
        checks = tested.get(case)
        if not isinstance(checks, dict) or any(checks.get(key) is not True for key in
                ('clean_install', 'upgrade', 'upgrade_launch', 'launch')):
            raise ReleaseUnavailable('installation_evidence_incomplete')
    return tested
''')
    replace_fn(name, '_require_android_floor', '''
def _require_android_floor(report: dict) -> None:
    if type(report.get('min_sdk')) is not int or report['min_sdk'] != 37:
        raise ReleaseUnavailable('unsupported_android_floor')
    if type(report.get('target_sdk')) is not int or report['target_sdk'] != 37:
        raise ReleaseUnavailable('unsupported_android_target')
''')
    replace_fn(name, '_require_transcript_match', '''
def _require_transcript_match(report: dict, tested: dict, *, sha256: str) -> None:
    if 'installation_tests' not in report:
        raise ReleaseUnavailable('runtime_installation_transcript_required')
    try:
        derived = from_ci_reports(report['installation_tests'], sha256)
    except InstallationEvidenceError as error:
        raise ReleaseUnavailable('installation_transcript_invalid') from error
    if tested != derived:
        raise ReleaseUnavailable('installation_transcript_conflict')
''')
    name = '.github/scripts/verify_apk.py'
    edit(name, 'Android 15+ build', 'Android 17+ build')
    edit(name, "sdkVersion:'35'", "sdkVersion:'37'")
    edit(name, "targetSdkVersion:'36'", "targetSdkVersion:'37'")
    edit(name, '"min_sdk": 35, "target_sdk": 36', '"min_sdk": 37, "target_sdk": 37')
    name = '.github/scripts/installation_report.py'
    edit(name, 'android_api: int | None = None)', 'android_api: int | None = None, page_size_bytes: int | None = None)')
    edit(name, '== TEST_NAME), android_api)', '== TEST_NAME), android_api, page_size_bytes=page_size_bytes)')
    name = '.github/scripts/test_apk_installation.py'
    edit(name, '    api: int,\n    work: Path,', '    api: int,\n    page_size_bytes: int,\n    work: Path,')
    edit(name, 'image = system_image(api)', 'image = system_image(api, page_size_bytes)')
    edit(name, 'snapshot_runtime_environment(device, sdk, api)', 'snapshot_runtime_environment(device, sdk, api, page_size_bytes=page_size_bytes)')
    edit(name, 'measured_record(api, page_size.stdout, candidate_digest)', 'measured_record(api, page_size.stdout, candidate_digest, page_size_bytes=page_size_bytes)')
    edit(name, 'if api in {35, 36} and os.getenv("RUN_PROFILE_UI_TESTS") == "1":', 'if api == 37 and os.getenv("RUN_PROFILE_UI_TESTS") == "1":')
    edit(name, 'parser.add_argument("--api", default=36, type=int)', 'parser.add_argument("--api", choices=(37,), default=37, type=int)\n    parser.add_argument("--page-size", choices=(4096, 16384), required=True, type=int)')
    edit(name, 'api=args.api,\n                work=', 'api=args.api,\n                page_size_bytes=args.page_size,\n                work=')
    text = read(name)
    text = replace(text, '    batch = ".bat" if os.name == "nt" else ""\n', '')
    start = text.index('    manager = str(')
    end = text.index('    name = f"analyst-install-', start)
    text = text[:start] + text[end:]
    start = text.index('    create = run(', start)
    end = text.index('    configure_userdata(', start)
    text = text[:start] + '    from emulator_profile import create_owned_profile\n    create_owned_profile(sdk, work, name, image)\n' + text[end:]
    changes[name] = text
    edit(name, '# API35 ps16k + Google services exhausted 2GiB: exit-info', '# Full UI and Google services require the measured memory budget: exit-info')
    edit(name, "# owned disk images before a retry, API36, or another runner's lease.", "# owned images before a retry, next page-size case, or another runner's lease.")
    name = '.github/scripts/emulator_runtime.py'
    text = re.sub(r'def snapshot_runtime_environment\(([^\n]*?)api: int\)',
                  r'def snapshot_runtime_environment(\1api: int, *, page_size_bytes: int)', read(name))
    if text == read(name):
        raise ValueError('Unexpected runtime snapshot signature')
    changes[name] = text.replace('system_image(api)', 'system_image(api, page_size_bytes)')
    for name in ('.github/workflows/android-ci.yml', '.github/workflows/android-apk.yml'):
        text = read(name).replace('SDK 36', 'SDK 37')
        text = text.replace('bin\\sdkmanager.bat" goto tools_ready', 'bin\\android.exe" goto tools_ready')
        start = text.index('          set "SDKMANAGER=')
        end = text.index('\n      - name:', start)
        text = text[:start] + '          py -3 .github\\scripts\\android_sdk.py --sdk "%ANDROID_SDK_ROOT%" --kind platform\n          if errorlevel 1 exit /b 1\n' + text[end:]
        text = text.replace('Android 15 and 16', 'Android 17 with 16 KB and 4 KB pages').replace('Android 15+', 'Android 17+')
        text = text.replace('install-api-35', 'install-api-37-16k').replace('install-api-36', 'install-api-37-4k')
        text = text.replace('ui-screens-api35', 'ui-screens-api37-16k')
        text = text.replace('Android 15/API 35 and Android 16/API 36', 'Android 17/API 37 16 KB and 4 KB')
        changes[name] = text
    name = '.github/actions/check-apk/action.yml'
    text = read(name).replace('Android 15 and 16 emulators', 'Android 17 emulators with independent 16 KB and 4 KB cases')
    text = text.replace('build-tools\\36.0.0', 'build-tools\\37.0.0')
    start = text.index('        set "YES_FILE=')
    end = text.index('\n    - name:', start)
    text = text[:start] + '        py -3 .github\\scripts\\android_sdk.py --sdk "%ANDROID_SDK_ROOT%" --kind runtime\n        if errorlevel 1 exit /b 1\n' + text[end:]
    text = text.replace('Android 15 with 16 KB pages', 'Android 17 with 16 KB pages').replace('Android 16', 'Android 17 with 4 KB pages')
    text = text.replace('--api 35', '--api 37 --page-size 16384').replace('--api 36', '--api 37 --page-size 4096')
    text = text.replace('install-api-35', 'install-api-37-16k').replace('install-api-36', 'install-api-37-4k').replace('ui-screens-api35', 'ui-screens-api37-16k')
    changes[name] = text
    edit('.github/scripts/private_apk_review.cjs', 'Android 15+', 'Android 17+')

    name = 'backend/tests/test_installation_evidence.py'
    replace_fn(name, 'reports', '''
def reports():
    from backend.tests.android17_fixtures import reports as matrix_reports
    return matrix_reports(CANDIDATE, PREVIOUS, UI_FIXTURE)
''')
    replace_fn(name, 'runtime_reports', 'def runtime_reports():\n    return reports()')
    replace_fn(name, 'test_android_16_and_exact_artifact', '''
def test_android17_and_exact_artifact(self):
    result = from_ci_reports(reports(), CANDIDATE)
    self.assertEqual(set(result), {'apk_sha256', 'runtime_schema', '37-16k', '37-4k'})
    for case, size in (('37-16k', 16384), ('37-4k', 4096)):
        self.assertEqual(result[case]['page_size_bytes'], size)
        self.assertTrue(result[case]['upgrade'])
        self.assertTrue(result[case]['launch'])
''', owner='EvidenceTests')
    replace_fn(name, 'test_android15_clean_launch_ui_and_android16_upgrade_are_distinct', '''
def test_both_page_size_cases_are_required(self):
    data = reports()
    self.reject(data[:1])
    self.reject(data[1:])
    self.reject([data[0], deepcopy(data[0])])
''', owner='EvidenceTests')
    replace_fn(name, 'test_android15_accepts_complete_upgrade_from_the_compatible_baseline', '''
def test_older_platform_is_rejected_even_with_complete_upgrade(self):
    for api in (35, 36):
        data = reports()
        data[0]['android_api'] = api
        next(r for r in data[0]['results'] if r['test'] == 'kernel_page_size')['android_api'] = api
        self.reject(data)
''', owner='EvidenceTests')
    replace_fn(name, 'test_android15_partial_upgrade_or_wrong_artifact_is_rejected', '''
def test_partial_upgrade_or_wrong_artifact_is_rejected(self):
    for index in (0, 1):
        for missing in ('previous_clean_install', 'upgrade_to_candidate', 'upgrade_bootstrap_launch'):
            data = reports()
            data[index]['results'] = [r for r in data[index]['results'] if r['test'] != missing]
            self.reject(data)
        for name in ('upgrade_to_candidate', 'upgrade_bootstrap_launch', 'previous_clean_install'):
            data = reports()
            record = next(r for r in data[index]['results'] if r['test'] == name)
            record['apk_sha256'] = CANDIDATE if name == 'previous_clean_install' else PREVIOUS
            self.reject(data)
''', owner='EvidenceTests')
    replace_fn(name, 'test_android15_does_not_replace_upgrade_or_allow_wrong_artifact', '''
def test_clean_run_does_not_replace_upgrade_or_allow_wrong_artifact(self):
    for index in (0, 1):
        for name in ('candidate_clean_install', 'activity_launch', 'profile_ui'):
            data = reports()
            data[index]['results'] = [r for r in data[index]['results'] if r['test'] != name]
            self.reject(data)
        data = reports()
        next(r for r in data[index]['results'] if r['test'] == 'candidate_clean_install')['apk_sha256'] = PREVIOUS
        self.reject(data)
''', owner='EvidenceTests')
    replace_fn(name, 'test_new_release_requires_real_16kb_and_4kb_full_matrix', '''
def test_new_release_requires_real_16kb_and_4kb_full_matrix(self):
    data = runtime_reports()
    checked = from_ci_reports(data, CANDIDATE)
    for key, size in (('37-16k', 16384), ('37-4k', 4096)):
        self.assertEqual(checked[key]['page_size_bytes'], size)
        self.assertEqual(checked[key]['runtime_16kb'], size == 16384)
        self.assertEqual(checked[key]['business_case_count'], 60)
        self.assertEqual(checked[key]['portfolio_case_count'], 14)
    self.reject([android15_report(), data[1]])
''', owner='EvidenceTests')
    edit(name, "self.assertIn('36', from_ci_reports(data, CANDIDATE))", "self.assertIn('37-16k', from_ci_reports(data, CANDIDATE))")
    edit(name, "for value in ('36', 36.0, True):", "for value in ('37', 37.0, True):")

    for path in sorted((root / 'backend/tests').glob('test_*.py')):
        name = path.relative_to(root).as_posix()
        text = read(name)
        edits = []
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.FunctionDef) or node.name not in {'report', 'evidence'}:
                continue
            fragment = ast.get_source_segment(text, node)
            if 'installation_evidence' not in fragment:
                continue
            for ret in ast.walk(node):
                if not isinstance(ret, ast.Return) or ret.value is None:
                    continue
                expression = ast.get_source_segment(text, ret.value)
                if 'installation_evidence' not in expression:
                    continue
                lines = text.splitlines(keepends=True)
                first = sum(len(line) for line in lines[:ret.value.lineno - 1]) + ret.value.col_offset
                last = sum(len(line) for line in lines[:ret.value.end_lineno - 1]) + ret.value.end_col_offset
                edits.append((first, last, 'adapt_publication(' + expression + ')'))
        if edits:
            for first, last, value in sorted(edits, reverse=True):
                text = text[:first] + value + text[last:]
            lines = text.splitlines(keepends=True)
            insert_at = 1 if lines[0].startswith('"""') and lines[0].rstrip().endswith('"""') else 0
            lines.insert(insert_at, 'from backend.tests.android17_fixtures import adapt_publication\n')
            changes[name] = ''.join(lines)
            print('ANDROID17_POSITIVE_FIXTURE=' + name)
    tracked = subprocess.check_output(['git', 'ls-files', '-z', '*.py'], cwd=root).decode().split('\0')
    for name in filter(None, tracked):
        text = read(name)
        migrated = text.replace(', require_runtime_16kb=True', '')
        if migrated != text:
            changes[name] = migrated
    for name, text in changes.items():
        if name.endswith('.py'):
            compile(text, name, 'exec')
    for name, text in changes.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8', newline='\n')
    (root / '.migration-result.json').write_text(json.dumps(sorted(changes), indent=2), encoding='utf-8')
    print('ANDROID17_MIGRATION_FILES=' + json.dumps(sorted(changes)))


if __name__ == '__main__':
    main()
