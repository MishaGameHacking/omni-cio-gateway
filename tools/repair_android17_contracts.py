"""One-shot exact-fragment correction; no SDK rewriting, deployments or secrets.

Changed source aborts before any output is written. A later integration removes
this one-shot migration utility rather than leaving another product entrypoint.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
EDITS = {
    '.github/scripts/prepare_android_sdk.py': [
        ('def _verify_package(root: Path, package: str) -> None:\n    directory =',
         'def _verify_package(root: Path, package: str) -> None:\n    root = root.resolve(strict=True)\n    directory ='),
        ("properties.get('AndroidVersion.ApiLevel') != str(COMPILE_SDK)",
         "properties.get('AndroidVersion.ApiLevel') not in {str(COMPILE_SDK), f'{COMPILE_SDK}.0'}"),
        ("    if package.startswith('system-images;') and properties.get('SystemImage.Abi') != 'x86_64':",
         "    if properties.get('AndroidVersion.PreviewSdkInt', '0') != '0':\n        raise RuntimeError('Preview SDK integer cannot replace the required release')\n    if properties.get('AndroidVersion.BetaVersion', ''):\n        raise RuntimeError('Beta SDK package cannot replace the required release')\n    if package.startswith('system-images;') and properties.get('SystemImage.Abi') != 'x86_64':"),
    ],
    '.github/scripts/tests/test_prepare_android_sdk.py': [
        ('        self.root.mkdir()\n', '        self.root.mkdir()\n        self.root = self.root.resolve(strict=True)\n'),
        ("other = Path(self.temp.name) / self.cli.name", "other = Path(self.temp.name).resolve(strict=True) / self.cli.name"),
    ],
    'backend/tests/test_client_updates.py': [
        ('from backend import client_updates as updates\n', 'from backend import client_updates as updates\nfrom backend.client_updates import ReleaseUnavailable\n'),
        ('result.min_android_api', 'result.min_sdk'),
    ],
    'backend/tests/test_release_rollover.py': [
        ("report['min_sdk'] = 37\n        with self.assertRaisesRegex(ReleaseUnavailable, 'identity_changed'):",
         "report['version_name'] = 'changed-name-for-same-version'\n        with self.assertRaisesRegex(ReleaseUnavailable, 'identity_changed'):"),
    ],
    'backend/tests/test_release_runtime_publication.py': [('result.min_android_api', 'result.min_sdk')],
    '.github/scripts/persistent_ui.py': [
        ('from contextlib import contextmanager\n', 'from contextlib import contextmanager\nfrom backend.android_runtime_contract import TARGET_SDK\n'),
        ('not in {"35", "36"}', '!= str(TARGET_SDK)'),
        ('Frame instrumentation requires a tested API 35 or 36 image', 'Frame instrumentation requires the current tested Android image'),
    ],
}
NEW_TESTS = '''    def test_official_api_base_notation_is_accepted(self):
        package = sdk.required_sdk_packages()[0]
        self.write_package(package)
        properties = self.root.joinpath(*package.split(';')) / 'source.properties'
        properties.write_text('AndroidVersion.ApiLevel=37.0\\nAndroidVersion.PreviewSdkInt=0\\n', encoding='utf-8')
        sdk._verify_package(self.root, package)

    def test_other_api_minor_and_preview_metadata_are_rejected(self):
        package = sdk.required_sdk_packages()[0]
        self.write_package(package)
        path = self.root.joinpath(*package.split(';')) / 'source.properties'
        invalid = ('AndroidVersion.ApiLevel=37.1\\n', 'AndroidVersion.ApiLevel=36.0\\n',
                   'AndroidVersion.ApiLevel=37.00\\n', 'AndroidVersion.ApiLevel=3.7e1\\n',
                   'AndroidVersion.ApiLevel=37.0\\nAndroidVersion.PreviewSdkInt=1\\n',
                   'AndroidVersion.ApiLevel=37.0\\nAndroidVersion.BetaVersion=beta1\\n')
        for metadata in invalid:
            path.write_text(metadata, encoding='utf-8')
            with self.subTest(metadata=metadata), self.assertRaises(RuntimeError):
                sdk._verify_package(self.root, package)

    def test_equivalent_parent_alias_is_normalized(self):
        package = sdk.required_sdk_packages()[0]
        self.write_package(package)
        child = self.root / 'child'
        child.mkdir()
        sdk._verify_package(child / '..', package)

'''


def main():
    prepared = {}
    for name, replacements in EDITS.items():
        text = (ROOT / name).read_text(encoding='utf-8')
        for old, new in replacements:
            if text.count(old) != 1:
                raise ValueError(f'Expected one reviewed fragment: {name}: {old[:100]}')
            text = text.replace(old, new, 1)
        prepared[name] = text
    name = '.github/scripts/tests/test_prepare_android_sdk.py'
    marker = "\n\nif __name__ == '__main__':"
    if prepared[name].count(marker) != 1:
        raise ValueError('SDK test entrypoint changed')
    prepared[name] = prepared[name].replace(marker, '\n\n' + NEW_TESTS + marker)
    for name, text in prepared.items():
        compile(text, name, 'exec')
    records = []
    for name, text in prepared.items():
        with (ROOT / name).open('w', encoding='utf-8', newline='\n') as target:
            target.write(text)
        records.append({'path': name})
    (ROOT / '.git/android17-refactor.json').write_text(json.dumps(records), encoding='utf-8')
    print('ANDROID17_REVIEWED_REPAIR=' + json.dumps(records))


if __name__ == '__main__':
    main()
