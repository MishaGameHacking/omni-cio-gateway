"""Install only the current project's SDK packages using the public Android CLI.

No fallback OS, beta image, emulator launch, APK publication or device mutation.
The separate runtime gate still measures the actual guest API and page size.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.android_runtime_contract import required_sdk_packages


def prepare(sdk: Path, *, runtime: bool) -> None:
    root = sdk.resolve(strict=True)
    executable = root / 'cmdline-tools' / 'latest' / 'bin' / ('android.exe' if os.name == 'nt' else 'android')
    if not executable.is_file():
        raise RuntimeError('Current Android CLI is required; bootstrap the pinned tools first')
    packages = required_sdk_packages()
    selected = packages[2:] if runtime else packages[:2]
    for package in selected:
        command = [str(executable), '--sdk=' + str(root), 'sdk', 'install', package.replace(';', '/')]
        print('ANDROID_SDK_REQUIRED_PACKAGE=' + package, flush=True)
        subprocess.run(command, input='y\n' * 200, text=True, check=True, timeout=600)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--runtime', action='store_true')
    args = parser.parse_args()
    prepare(args.sdk, runtime=args.runtime)


if __name__ == '__main__':
    main()
