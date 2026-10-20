"""Apply the owner-requested Android 17 migration on its isolated review branch.

This edits tracked source, not runtime data or devices. It cannot publish an APK,
change main, use cloud credentials or weaken a test result. Generated edits must
pass independent CI before integration. Historical reports are not rewritten.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BRANCH = 'audit/android17-project-20261020'


class Changes:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.contents: dict[str, str] = {}

    def path(self, name: str) -> Path:
        path = self.root / name
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValueError('Unsafe migration path: ' + name)
        return path

    def read(self, name: str) -> str:
        if name not in self.contents:
            self.contents[name] = self.path(name).read_text(encoding='utf-8')
        return self.contents[name]

    def replace(self, name: str, old: str, new: str, count: int = 1) -> None:
        text = self.read(name)
        if text.count(old) != count:
            raise ValueError(f'Migration precondition failed in {name}: {old[:80]!r}')
        self.contents[name] = text.replace(old, new)

    def optional(self, name: str, old: str, new: str) -> None:
        text = self.read(name)
        if old in text:
            self.replace(name, old, new, text.count(old))

    def write(self, name: str, text: str) -> None:
        self.path(name)
        self.contents[name] = text

    def finish(self) -> None:
        changed = []
        for name, text in self.contents.items():
            if name.endswith('.py'):
                compile(text, name, 'exec')
            path = self.path(name)
            if not path.exists() or path.read_text(encoding='utf-8') != text:
                changed.append(name)
        for name in changed:
            path = self.path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.contents[name], encoding='utf-8', newline='\n')
        report = [{'path': name, 'sha256': hashlib.sha256(self.contents[name].encode()).hexdigest()}
                  for name in sorted(changed)]
        (self.root / '.git' / 'android17-refactor.json').write_text(json.dumps(report), encoding='utf-8')
        print('ANDROID17_SOURCE_CHANGES=' + json.dumps([row['path'] for row in report]))


def migrate_modules(changes: Changes) -> None:
    for name in ('app/build.gradle.kts', 'ci-ui-driver/build.gradle.kts'):
        for old, new in (('compileSdk = 36', 'compileSdk = 37'),
                         ('minSdk = 35', 'minSdk = 37'), ('targetSdk = 36', 'targetSdk = 37')):
            changes.optional(name, old, new)
        text = changes.read(name)
        for field in ('compileSdk', 'minSdk', 'targetSdk'):
            if re.findall(r'\b' + field + r'\s*=\s*(\d+)', text) != ['37']:
                raise ValueError('Ambiguous SDK field: ' + name + ':' + field)
        if 'buildToolsVersion' not in text:
            changes.replace(name, '    compileSdk = 37\n', '    compileSdk = 37\n    buildToolsVersion = "37.0.0"\n')
    name = 'ci-ui-driver/src/main/java/ru/omnicio/ciframe/FrameInstrumentation.java'
    old = '''    @SuppressWarnings("deprecation")
    private static boolean checkedState(AccessibilityNodeInfo node) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.BAKLAVA) {
            return node.getChecked() == AccessibilityNodeInfo.CHECKED_STATE_TRUE;
        }
        // Public API35 contract; getChecked() only exists from API36.
        return node.isChecked();
    }'''
    new = '''    private static boolean checkedState(AccessibilityNodeInfo node) {
        return node.getChecked() == AccessibilityNodeInfo.CHECKED_STATE_TRUE;
    }'''
    changes.replace(name, old, new)
    changes.replace(name, 'import android.os.Build;\n', '')
    name = 'app/src/main/AndroidManifest.xml'
    changes.replace(name, 'android:usesCleartextTraffic="false"',
                    'android:networkSecurityConfig="@xml/network_security_config"')
    changes.write('app/src/main/res/xml/network_security_config.xml', '''<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>
</network-security-config>
''')


def migrate_installer(changes: Changes) -> None:
    name = '.github/scripts/test_apk_installation.py'
    changes.replace(name, '    attempt: int,\n) -> list[dict[str, object]]:',
                    '    attempt: int,\n    page_size_bytes: int = 4096,\n) -> list[dict[str, object]]:')
    changes.replace(name, 'image = system_image(api)', 'image = system_image(api, page_size_bytes)')
    changes.replace(name, 'snapshot_runtime_environment(device, sdk, api)',
                    'snapshot_runtime_environment(device, sdk, api, page_size_bytes=page_size_bytes)')
    changes.replace(name, 'measured_record(api, page_size.stdout, candidate_digest)',
                    'measured_record(api, page_size.stdout, candidate_digest, page_size_bytes=page_size_bytes)')
    changes.replace(name, 'if api in {35, 36} and ', 'if ')
    changes.replace(name, 'parser.add_argument("--api", default=36, type=int)',
                    'parser.add_argument("--api", type=int, choices=(37,), default=37)\n    parser.add_argument("--page-bytes", type=int, choices=(4096, 16384), default=4096)')
    changes.replace(name, '                attempt=attempt,\n',
                    '                attempt=attempt,\n                page_size_bytes=args.page_bytes,\n')
    changes.optional(name, 'API35', 'current OS')
    changes.optional(name, 'API36', 'other page-size profile')
    name = '.github/scripts/emulator_runtime.py'
    changes.replace(name, 'api: int) -> dict:', 'api: int, *, page_size_bytes: int = 4096) -> dict:')
    changes.replace(name, 'image = system_image(api)', 'image = system_image(api, page_size_bytes)')
    name = '.github/scripts/installation_report.py'
    changes.replace(name, 'android_api: int | None = None) -> None:',
                    'android_api: int | None = None, page_size_bytes: int = 4096) -> None:')
    changes.replace(name, '), android_api)', '), android_api, page_size_bytes=page_size_bytes)')


def migrate_static_verifier(changes: Changes) -> None:
    name = '.github/scripts/verify_apk.py'
    changes.replace(name, 'Unsupported DEX version for the Android 15+ build',
                    'Unsupported DEX format in the current Android build')
    changes.replace(name, 'require("sdkVersion:\'35\'" in badging, "Unexpected minimum Android version")',
                    'require(_sdk_value(badging, "sdkVersion") == 37, "Unexpected minimum Android version")')
    changes.replace(name, 'require("targetSdkVersion:\'36\'" in badging, "Unexpected target Android version")',
                    'require(_sdk_value(badging, "targetSdkVersion") == 37, "Unexpected target Android version")')
    changes.replace(name, '"min_sdk": 35, "target_sdk": 36', '"min_sdk": 37, "target_sdk": 37')
    helper = '''def _sdk_value(badging: str, field: str) -> int:
    matches = re.findall(r"^" + re.escape(field) + r":'([0-9]+)'$", badging, re.MULTILINE)
    require(len(matches) == 1, "Missing or ambiguous SDK metadata")
    return int(matches[0])


'''
    changes.replace(name, 'def check_manifest(', helper + 'def check_manifest(')


def migrate_workflow_metadata(changes: Changes) -> None:
    paths = ('.github/workflows/android-ci.yml', '.github/workflows/android-apk.yml',
             '.github/workflows/android-diagnostics.yml', '.github/actions/check-apk/action.yml')
    replacements = (
        ('Android SDK 36', 'Android SDK 37'),
        ('platforms;android-36', 'platforms;android-37.0'),
        ('platforms\\android-36', 'platforms\\android-37.0'),
        ('build-tools;36.0.0', 'build-tools;37.0.0'),
        ('build-tools\\36.0.0', 'build-tools\\37.0.0'),
        ('system-images;android-35;google_apis_ps16k;x86_64', 'system-images;android-37.0;google_apis_ps16k;x86_64'),
        ('system-images;android-36;google_apis;x86_64', 'system-images;android-37.0;google_apis;x86_64'),
        ('--api 35', '--api 37 --page-bytes 16384'), ('--api 36', '--api 37 --page-bytes 4096'),
        ('install-api-35', 'install-api37-16384'), ('install-api-36', 'install-api37-4096'),
        ('ui-screens-api35', 'ui-screens-api37-16384'),
        ('Android 15 and 16', 'Android 17 with both page-size profiles'),
        ('Android 15 with 16 KB', 'Android 17 with 16 KB'),
        ('Android 16', 'Android 17 with 4 KB pages'),
    )
    for name in paths:
        if changes.path(name).exists():
            for old, new in replacements:
                changes.optional(name, old, new)


def main() -> None:
    branch = subprocess.run(['git', 'symbolic-ref', '--short', 'HEAD'], cwd=ROOT,
                            text=True, capture_output=True, check=True).stdout.strip()
    if branch != BRANCH:
        raise ValueError('Migration writes are restricted to the dedicated review branch')
    changes = Changes(ROOT)
    migrate_modules(changes)
    migrate_installer(changes)
    migrate_static_verifier(changes)
    migrate_workflow_metadata(changes)
    changes.finish()


if __name__ == '__main__':
    main()
