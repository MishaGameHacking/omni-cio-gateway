"""Install only the explicit Android 17 SDK packages using Android CLI."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

CHECKOUT = Path(__file__).resolve().parents[2]
if str(CHECKOUT) not in sys.path:
    sys.path.insert(0, str(CHECKOUT))
from backend.android_platform import BUILD_TOOLS, RUNTIME_TARGETS, SDK_PLATFORM


def packages(kind: str) -> tuple[str, ...]:
    if kind == 'platform':
        return (f'platforms/{SDK_PLATFORM}@2', f'build-tools/{BUILD_TOOLS}')
    if kind == 'runtime':
        return ('emulator', 'platform-tools', *(target.system_image.replace(';', '/') +
                ('@7' if target.page_size_bytes == 16_384 else '@6') for target in RUNTIME_TARGETS))
    raise ValueError('Unknown SDK package group')


def command(sdk: Path, kind: str) -> list[str]:
    executable = sdk / 'cmdline-tools' / 'latest' / 'bin' / ('android.exe' if os.name == 'nt' else 'android')
    return [str(executable), '--no-metrics', f'--sdk={sdk}', 'sdk', '--ignore-outdated-xmls',
            'install', *packages(kind)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--kind', choices=('platform', 'runtime'), required=True)
    args = parser.parse_args()
    sdk = args.sdk.resolve(strict=True)
    argv = command(sdk, args.kind)
    if not Path(argv[0]).is_file():
        raise RuntimeError('Android CLI is missing from the verified command-line tools installation')
    print('ANDROID17_SDK_PACKAGES=' + ','.join(packages(args.kind)), flush=True)
    subprocess.run(argv, input='y\n' * 40, text=True, check=True, timeout=900)


if __name__ == '__main__':
    main()
