"""Prepare reviewed workflow diffs as Git objects; integration needs workflows permission.

Only two fixed workflows can be edited. This never updates a Git ref, publishes
an artifact, starts a device or contacts production. Existing evidence retention
and explicit release opt-in remain byte-for-byte except runtime profile paths.
"""
from __future__ import annotations
import json
import textwrap
from migrate_android17 import ROOT, Changes

PATHS = ('.github/workflows/android-ci.yml', '.github/workflows/android-apk.yml')
SDK_STEP = '''
      - name: Ensure Android SDK 37 is installed
        shell: cmd
        run: |
          if exist "%ANDROID_SDK_ROOT%\\cmdline-tools\\latest\\bin\\android.exe" goto tools_ready
          set "TOOLS_ZIP=%RUNNER_TEMP%\\commandlinetools-win-15859902_latest.zip"
          curl.exe -fL --retry 3 --retry-delay 2 "https://dl.google.com/android/repository/commandlinetools-win-15859902_latest.zip" -o "%TOOLS_ZIP%"
          if errorlevel 1 exit /b 1
          certutil -hashfile "%TOOLS_ZIP%" SHA256 > "%TOOLS_ZIP%.sha256"
          if errorlevel 1 exit /b 1
          findstr /I /C:"90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a" "%TOOLS_ZIP%.sha256" >nul
          if errorlevel 1 exit /b 1
          if not exist "%ANDROID_SDK_ROOT%\\cmdline-tools" mkdir "%ANDROID_SDK_ROOT%\\cmdline-tools"
          tar.exe -xf "%TOOLS_ZIP%" -C "%ANDROID_SDK_ROOT%\\cmdline-tools"
          if errorlevel 1 exit /b 1
          if exist "%ANDROID_SDK_ROOT%\\cmdline-tools\\latest" rmdir /s /q "%ANDROID_SDK_ROOT%\\cmdline-tools\\latest"
          move "%ANDROID_SDK_ROOT%\\cmdline-tools\\cmdline-tools" "%ANDROID_SDK_ROOT%\\cmdline-tools\\latest"
          if errorlevel 1 exit /b 1
          :tools_ready
          py -3 .github\\scripts\\prepare_android_sdk.py --sdk "%ANDROID_SDK_ROOT%"
          if errorlevel 1 exit /b 1

'''


def prepare(changes: Changes, name: str) -> None:
    text = changes.read(name)
    start = text.index('      - name: Ensure Android SDK 36 is installed\n')
    end = text.index('      - name: Test APK verification rules\n', start)
    text = text[:start] + textwrap.indent(textwrap.dedent(SDK_STEP).lstrip(), '      ') + text[end:]
    for old, new in (
        ('Android 15 and 16', 'Android 17 with both page-size profiles'),
        ('API35 16KB/API36', 'API37 16KB/4KB'),
        ('install-api-35', 'install-api37-16384'), ('install-api-36', 'install-api37-4096'),
        ('ui-screens-api35', 'ui-screens-api37-16384'),
        ('platforms;android-36', 'platforms;android-37.0'),
        ('build-tools;36.0.0', 'build-tools;37.0.0'),
    ):
        text = text.replace(old, new)
    marker = '      - "backend/installation_evidence.py"\n'
    if marker in text:
        text = text.replace(marker, marker + '      - "backend/android_runtime_contract.py"\n')
    else:
        marker = '      - "tools/**"\n'
        if marker not in text:
            raise ValueError('Expected source trigger missing: ' + name)
        text = text.replace(marker, marker + '      - "backend/android_runtime_contract.py"\n')
    for stale in ('--api 35', '--api 36', 'Android 15 and 16', 'Ensure Android SDK 36'):
        if stale in text:
            raise ValueError('Unmigrated executable workflow policy: ' + stale)
    changes.write(name, text)


def main() -> None:
    changes = Changes(ROOT)
    for name in PATHS:
        prepare(changes, name)
    changes.finish()
    print('WORKFLOW_DIFF_PATHS=' + json.dumps(PATHS))


if __name__ == '__main__':
    main()
