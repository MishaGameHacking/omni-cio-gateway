"""Install and verify the current SDK, without an older-platform fallback.

ANDROID_CLI_PATH may select a runner-managed native Android CLI outside the SDK.
The default SDK-local location remains supported. No download-and-execute bootstrap,
SDK downgrade, emulator launch, APK publication or production access occurs here.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.android_runtime_contract import COMPILE_SDK, required_sdk_packages

TOOL_TIMEOUT_SECONDS = 600
MAX_PROPERTIES_BYTES = 65_536


def _cli(root: Path) -> Path:
    configured = os.environ.get('ANDROID_CLI_PATH')
    executable = (Path(configured) if configured else root / 'cmdline-tools' /
                  'latest' / 'bin' / ('android.exe' if os.name == 'nt' else 'android'))
    if not executable.is_absolute() or not executable.is_file():
        raise RuntimeError('Current Android CLI is required; configure an absolute ANDROID_CLI_PATH')
    if executable.suffix.lower() in {'.bat', '.cmd'}:
        raise RuntimeError('ANDROID_CLI_PATH must identify the native CLI, not a shell script')
    return executable.resolve(strict=True)


def _payloads(package: str) -> tuple[str, ...]:
    suffix = '.exe' if os.name == 'nt' else ''
    family = package.split(';', 1)[0]
    required = {
        'platforms': ('android.jar', 'source.properties'),
        'build-tools': (f'aapt{suffix}', f'aapt2{suffix}', f'zipalign{suffix}', 'lib/apksigner.jar'),
        'platform-tools': (f'adb{suffix}',),
        'emulator': (f'emulator{suffix}',),
        'system-images': ('system.img', 'source.properties'),
    }
    if family not in required:
        raise ValueError('Unsupported SDK package family')
    return required[family]


def _properties(path: Path) -> dict[str, str]:
    with path.open('rb') as source:
        raw = source.read(MAX_PROPERTIES_BYTES + 1)
    if len(raw) > MAX_PROPERTIES_BYTES:
        raise RuntimeError('SDK source.properties is oversized')
    result: dict[str, str] = {}
    for line in raw.decode('utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(('#', '!')):
            continue
        key, separator, value = stripped.partition('=')
        if not separator:
            raise RuntimeError('SDK source.properties is malformed')
        key, value = key.strip(), value.strip()
        if not key or key in result:
            raise RuntimeError('SDK source.properties contains ambiguous keys')
        result[key] = value
    return result


def _verify_package(root: Path, package: str) -> None:
    directory = root.joinpath(*package.split(';'))
    for relative in _payloads(package):
        path = directory / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f'SDK package payload missing: {package}/{relative}')
        if not path.resolve(strict=True).is_relative_to(root):
            raise RuntimeError('SDK package payload escapes the selected SDK root')
    if package.startswith(('platforms;', 'system-images;')):
        _verify_platform_metadata(directory, package)


def _verify_platform_metadata(directory: Path, package: str) -> None:
    properties = _properties(directory / 'source.properties')
    if properties.get('AndroidVersion.ApiLevel') != str(COMPILE_SDK):
        raise RuntimeError('Installed SDK package API does not match the project')
    if properties.get('AndroidVersion.CodeName', 'REL') not in {'', 'REL'}:
        raise RuntimeError('Preview SDK package cannot replace the required release')
    if package.startswith('system-images;') and properties.get('SystemImage.Abi') != 'x86_64':
        raise RuntimeError('Installed emulator image has an unexpected ABI')


def prepare(sdk: Path, *, runtime: bool) -> None:
    if type(runtime) is not bool:
        raise ValueError('runtime must be boolean')
    root = sdk.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('SDK root must be a directory')
    executable = _cli(root)
    packages = required_sdk_packages()
    selected = packages[2:] if runtime else packages[:2]
    for package in selected:
        command = [str(executable), '--sdk=' + str(root), 'sdk', 'install', package.replace(';', '/')]
        print('ANDROID_SDK_REQUIRED_PACKAGE=' + package, flush=True)
        subprocess.run(command, input='y\n' * 200, text=True, check=True, timeout=TOOL_TIMEOUT_SECONDS)
        _verify_package(root, package)
    print('ANDROID17_SDK_PAYLOADS_VERIFIED=' + str(len(selected)), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--runtime', action='store_true')
    args = parser.parse_args()
    prepare(args.sdk, runtime=args.runtime)


if __name__ == '__main__':
    main()
