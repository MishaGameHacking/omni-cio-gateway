from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def path(name: str) -> Path:
    return ROOT / name


def read(name: str) -> str:
    return path(name).read_text(encoding="utf-8")


def write(name: str, text: str) -> None:
    path(name).write_text(text, encoding="utf-8", newline="\n")


def replace_once(name: str, old: str, new: str) -> None:
    text = read(name)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{name}: expected one match, found {count}: {old!r}")
    write(name, text.replace(old, new, 1))


def replace_all(name: str, old: str, new: str, minimum: int = 1) -> None:
    text = read(name)
    count = text.count(old)
    if count < minimum:
        raise RuntimeError(f"{name}: expected at least {minimum} matches, found {count}: {old!r}")
    write(name, text.replace(old, new))


def main() -> None:
    replace_once("app/build.gradle.kts", "minSdk = 33", "minSdk = 36")
    replace_once("app/build.gradle.kts", "versionCode = 25", "versionCode = 26")
    replace_once("app/build.gradle.kts", 'versionName = "0.7.0"', 'versionName = "0.7.1"')

    old_android = "\n".join([
        "- Минимальная поддерживаемая версия устройства: Android 13 / API 33.",
        "- Приложение проектируется для Android 13 и новее.",
        "- `compileSdk` и `targetSdk` поддерживать современными и обновлять по мере развития Android/toolchain.",
        "- Использовать актуальные стабильные публичные Android API.",
        "- Если API устарел и существует современная поддерживаемая альтернатива, использовать современную альтернативу.",
        "- Не использовать deprecated/legacy/non-SDK подход только ради совместимости со старыми Android, если на Android 13+ существует нормальный современный способ.",
        "- Основной стек Android: Kotlin, Jetpack Compose, Gradle Kotlin DSL. Другие языки и технологии использовать, когда они действительно нужны задаче.",
    ])
    new_android = "\n".join([
        "- Минимальная поддерживаемая версия устройства: **Android 16 / API 36**.",
        "- Android 15 / API 35 и все более старые версии не поддерживаются и не должны устанавливать приложение.",
        "- `minSdk`, `compileSdk` и `targetSdk` текущей линии держать не ниже API 36; повышать их при переходе на более новые стабильные Android.",
        "- Использовать стабильные публичные возможности Android 16 и новее без fallback-кода, polyfill и обходов, существующих только ради Android 15 и ниже.",
        "- Deprecated, legacy и non-SDK API не использовать, когда в Android 16+ есть актуальная публичная альтернатива.",
        "- Проверки установки, обновления, запуска и интерфейса выполнять на Android 16 / API 36 или более новой поддерживаемой версии; API 33–35 не являются релизной матрицей.",
        "- Основной стек Android: Kotlin, Jetpack Compose, Gradle Kotlin DSL. Другие языки и технологии использовать, когда они действительно нужны задаче.",
    ])
    replace_once("AGENTS.md", old_android, new_android)

    replace_once(
        "README.md",
        "Kotlin / Jetpack Compose. Android 13+ (`minSdk 33`), `compileSdk/targetSdk 36`.\n"
        "Текущая ветка интерфейса: **0.7.0 / versionCode 24**.",
        "Kotlin / Jetpack Compose. Android 16+ (`minSdk/compileSdk/targetSdk 36`).\n"
        "Текущая ветка интерфейса: **0.7.1 / versionCode 26**.",
    )
    replace_once(
        "README.md",
        "и запуск на Android 13/16.",
        "и запуск на Android 16.",
    )

    replace_once(
        ".github/actions/check-apk/action.yml",
        "description: Verify the fixed preview artifact, upgrade path, launch, and UI on disposable Android 13 and 16 emulators.",
        "description: Verify the fixed preview artifact, upgrade path, launch, and UI on a disposable Android 16 emulator.",
    )
    replace_once(
        ".github/actions/check-apk/action.yml",
        '        call "%ANDROID_SDK_ROOT%\\cmdline-tools\\latest\\bin\\sdkmanager.bat" --sdk_root="%ANDROID_SDK_ROOT%" --channel=0 "emulator" "platform-tools" "system-images;android-33;google_apis;x86_64" "system-images;android-36;google_apis;x86_64" < "%YES_FILE%"',
        '        call "%ANDROID_SDK_ROOT%\\cmdline-tools\\latest\\bin\\sdkmanager.bat" --sdk_root="%ANDROID_SDK_ROOT%" --channel=0 "emulator" "platform-tools" "system-images;android-36;google_apis;x86_64" < "%YES_FILE%"',
    )
    old_api33_step = "\n".join([
        "    - name: Test upgrade, clean install, launch, and profile UI on Android 13",
        "      shell: cmd",
        "      env:",
        "        PYTHONIOENCODING: utf-8",
        "        PYTHONUNBUFFERED: '1'",
        "      run: |",
        '        set "APK_DIR=%GITHUB_WORKSPACE%\\app\\build\\outputs\\apk\\preview"',
        '        py -3 .github\\scripts\\test_apk_installation.py --sdk "%ANDROID_SDK_ROOT%" --apk "%APK_DIR%\\app-preview.apk" --previous "%PREVIOUS_APK%" --api 33 --work-dir "%APK_DIR%\\install-api-33"',
        "        if errorlevel 1 exit /b 1",
        "",
    ])
    replace_once(".github/actions/check-apk/action.yml", old_api33_step, "")
    replace_once(
        ".github/actions/check-apk/action.yml",
        "    - name: Test upgrade, clean install, and launch on Android 16",
        "    - name: Test upgrade, clean install, launch, and profile UI on Android 16",
    )

    replace_once(
        ".github/scripts/test_apk_installation.py",
        'parser.add_argument("--api", default=33, type=int)',
        'parser.add_argument("--api", default=36, type=int)',
    )
    replace_once(
        ".github/scripts/test_apk_installation.py",
        'if args.api == 33 and os.getenv("RUN_PROFILE_UI_TESTS") == "1":',
        'if args.api == 36 and os.getenv("RUN_PROFILE_UI_TESTS") == "1":',
    )

    replace_once(
        ".github/scripts/validate_distribution.py",
        'require(api in (33, 36), "Unexpected emulator API")',
        'require(api == 36, "Unexpected emulator API")',
    )
    replace_once(
        ".github/scripts/validate_distribution.py",
        'profile_required = api == 33 and os.getenv("RUN_PROFILE_UI_TESTS") == "1"',
        'profile_required = os.getenv("RUN_PROFILE_UI_TESTS") == "1"',
    )
    replace_once(
        ".github/scripts/validate_distribution.py",
        'report["installation_tests"] = [checked_installation(33), checked_installation(36)]',
        'report["installation_tests"] = [checked_installation(36)]',
    )

    replace_once(
        ".github/scripts/verify_apk.py",
        '"Unsupported Android 13 DEX version"',
        '"Unsupported DEX version for the Android 16 build"',
    )
    replace_once(
        ".github/scripts/verify_apk.py",
        'require("sdkVersion:\'33\'" in badging, "Unexpected minimum Android version")',
        'require("sdkVersion:\'36\'" in badging, "Unexpected minimum Android version")',
    )
    replace_once(
        ".github/scripts/verify_apk.py",
        '"min_sdk": 33, "target_sdk": 36',
        '"min_sdk": 36, "target_sdk": 36',
    )
    replace_once(
        ".github/scripts/tests/test_verify_apk.py",
        '"sdkVersion:\'33\'\\ntargetSdkVersion:\'36\'"',
        '"sdkVersion:\'36\'\\ntargetSdkVersion:\'36\'"',
    )

    replace_once(
        "backend/installation_evidence.py",
        '"""Validate actual CI transcript shape; never infer installation from a build.',
        '"""Validate the actual Android 16 CI transcript; never infer installation from a build.',
    )
    old_profile = "\n".join([
        "    if run['android_api'] == 33:",
        "        if not run['profile_ui_required'] or not {'debug_ui_fixture_install', 'profile_ui'} <= records.keys():",
        "            raise InstallationEvidenceError('profile_ui_evidence_missing')",
    ])
    new_profile = "\n".join([
        "    if run['android_api'] != 36:",
        "        raise InstallationEvidenceError('unsupported_android_version')",
        "    if not run['profile_ui_required'] or not {'debug_ui_fixture_install', 'profile_ui'} <= records.keys():",
        "        raise InstallationEvidenceError('profile_ui_evidence_missing')",
    ])
    replace_once("backend/installation_evidence.py", old_profile, new_profile)
    replace_once(
        "backend/installation_evidence.py",
        '"""Reduce two checked API-specific transcripts to the canonical publisher contract."""',
        '"""Reduce one checked Android 16 transcript to the publisher contract."""',
    )
    replace_once(
        "backend/installation_evidence.py",
        "if not isinstance(installations, list) or len(installations) != 2:\n"
        "        raise InstallationEvidenceError('both_android_versions_required')",
        "if not isinstance(installations, list) or len(installations) != 1:\n"
        "        raise InstallationEvidenceError('android_16_evidence_required')",
    )
    replace_once(
        "backend/installation_evidence.py",
        "if type(api) is not int or api not in (33, 36) or str(api) in result:",
        "if type(api) is not int or api != 36 or str(api) in result:",
    )

    replace_once(
        "backend/release_publication.py",
        "    for api in ('33', '36'):\n",
        "    for api in ('36',):\n",
    )
    replace_once(
        "backend/release_publication.py",
        "    if 'installation_tests' in report:\n",
        "    if report.get('min_sdk') != 36:\n"
        "        raise ReleaseUnavailable('unsupported_android_floor')\n"
        "    if 'installation_tests' in report:\n",
    )

    test_path = "backend/tests/test_installation_evidence.py"
    replace_once(test_path, "for api in (33, 36):", "for api in (36,):")
    replace_once(test_path, "if api == 33:", "if api == 36:")
    replace_once(test_path, "'profile_ui_required': api == 33", "'profile_ui_required': api == 36")
    replace_once(test_path, "{'apk_sha256', '33', '36'}", "{'apk_sha256', '36'}")
    replace_once(test_path, "result['33']", "result['36']")
    replace_all(test_path, "data[1]", "data[0]")
    replace_once(test_path, "self.reject(reports()[:1])", "self.reject([])")

    for name in (
        "backend/tests/test_client_updates.py",
        "backend/tests/test_update_integration.py",
        "backend/tests/test_release_recovery.py",
        "backend/tests/test_release_rollover.py",
    ):
        text = read(name)
        text = text.replace("min_sdk=33", "min_sdk=36")
        text = text.replace("'min_sdk': 33", "'min_sdk': 36")
        text = text.replace(", '33': checks, '36': checks", ", '36': checks")
        text = re.sub(
            r"'33'\s*:\s*\{\s*'clean_install'\s*:\s*True\s*,\s*"
            r"'upgrade'\s*:\s*True\s*,\s*'launch'\s*:\s*True\s*\}\s*,\s*",
            "",
            text,
        )
        write(name, text)

    replace_once(
        ".github/workflows/android-apk.yml",
        '          if not exist "app\\build\\outputs\\apk\\preview\\install-api-33\\install-results.json" exit /b 1\n',
        "",
    )
    replace_all(
        ".github/workflows/android-apk.yml",
        "            app/build/outputs/apk/preview/install-api-33/install-results.json\n",
        "",
        minimum=1,
    )
    replace_once(
        ".github/workflows/android-apk.yml",
        "'Signed, non-debuggable preview APK. Android 13+; application ID ru.omnicio.app.debug.',",
        "'Signed, non-debuggable preview APK. Android 16+ only; application ID ru.omnicio.app.debug.',",
    )
    replace_once(
        ".github/workflows/android-apk.yml",
        "'APK signature, ZIP/ELF alignment, DEX integrity, clean installation, upgrade from the installed 0.5.1 preview, launch on Android 13/16 x86_64 emulators, and profile/education UI on Android 13 verified.',",
        "'APK signature, ZIP/ELF alignment, DEX integrity, clean installation, upgrade from the installed 0.5.1 preview, launch and profile/education UI on an Android 16 x86_64 emulator verified.',",
    )

    replace_once(
        ".github/workflows/android-ci.yml",
        "const names = ['apk-verification.json', 'install-api-33/install-results.json', 'install-api-36/install-results.json',",
        "const names = ['apk-verification.json', 'install-api-36/install-results.json',",
    )

    replace_once(
        ".github/scripts/build_release_manifest.py",
        'sdk = _integer(report["min_sdk"], 33, 1000, "invalid_min_sdk")',
        'sdk = _integer(report["min_sdk"], 36, 1000, "invalid_min_sdk")',
    )
    replace_once(
        ".github/scripts/tests/test_manifest_paths.py",
        'package="ru.omnicio.app.debug", min_sdk=33, sha256="a" * 64,',
        'package="ru.omnicio.app.debug", min_sdk=36, sha256="a" * 64,',
    )

    replace_once(
        "docs/UPDATES_AND_PORTFOLIO_RESEARCH.md",
        "установки, обновления и запуска на API 33 и 36",
        "установки, обновления и запуска на API 36",
    )
    replace_once(
        "docs/UPDATE_RUNTIME_UNIFICATION.md",
        "Android 13 and Android 16",
        "Android 16",
    )

    active = "\n".join(
        read(name)
        for name in (
            "app/build.gradle.kts",
            "AGENTS.md",
            "README.md",
            ".github/actions/check-apk/action.yml",
            ".github/scripts/test_apk_installation.py",
            ".github/scripts/validate_distribution.py",
            ".github/scripts/verify_apk.py",
            ".github/workflows/android-apk.yml",
            ".github/workflows/android-ci.yml",
            "backend/installation_evidence.py",
            "backend/release_publication.py",
        )
    )
    for marker in (
        "minSdk = 33",
        "install-api-33",
        "system-images;android-33",
        "api in (33, 36)",
        "checked_installation(33)",
        "args.api == 33",
        "Android 13+",
    ):
        if marker in active:
            raise RuntimeError(f"stale Android 13 release marker remains: {marker}")
    if "minSdk = 36" not in read("app/build.gradle.kts"):
        raise RuntimeError("Android 16 minimum was not applied")
    if "versionCode = 26" not in read("app/build.gradle.kts"):
        raise RuntimeError("versionCode was not advanced")


if __name__ == "__main__":
    main()
