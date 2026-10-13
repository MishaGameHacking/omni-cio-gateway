"""This guard keeps a migration checkpoint from publishing a mismatched updater."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('legacy_release_guard', Path(__file__).resolve().parents[1] / 'legacy_release_guard.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class LegacyReleaseGuardTests(unittest.TestCase):
    def test_canonical_runtime_stops_legacy_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'app/src/main/java/ru/omnicio/app/data/updates/UpdateProtocol.kt'
            source.parent.mkdir(parents=True)
            source.write_text('synthetic source marker', encoding='utf-8')
            with self.assertRaises(module.LegacyReleaseBlocked):
                module.require_legacy_runtime(root)
            self.assertEqual(source.read_text(encoding='utf-8'), 'synthetic source marker')

    def test_guard_does_not_order_or_create_resources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module.require_legacy_runtime(root)
            self.assertEqual(list(root.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
