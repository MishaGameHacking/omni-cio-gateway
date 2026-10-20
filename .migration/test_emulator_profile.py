"""Owned profile creation tests with a fake CLI, not runtime acceptance."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emulator_profile import create_owned_profile

IMAGE = 'system-images;android-37.0;google_apis;x86_64'
NAME = 'analyst-install-123-1'


class OwnedProfileTests(unittest.TestCase):
    def setUp(self):
        self.environment_home = os.environ.get('ANDROID_AVD_HOME')
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.sdk = self.root / 'sdk'
        self.work = self.root / 'work'
        self.work.mkdir()
        directory = self.sdk.joinpath(*IMAGE.split(';'))
        directory.mkdir(parents=True)
        (directory / 'system.img').write_bytes(b'synthetic, not an Android image')
        self.calls = []

    def fake_cli(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        home = Path(kwargs['env']['ANDROID_AVD_HOME'])
        profile = home / 'Medium_Phone_API_37.avd'
        profile.mkdir()
        (profile / 'config.ini').write_text('hw.lcd.width=1080\nhw.cpu.arch=arm64\nhw.sdCard.path=/foreign\nimage.sysdir.1=/foreign\n', encoding='utf-8')
        (profile / 'userdata.img').write_bytes(b'must not be reused')
        return subprocess.CompletedProcess(argv, 0, 'created')

    def create(self, **changes):
        args = dict(sdk=self.sdk, work=self.work, name=NAME, image=IMAGE, run=self.fake_cli)
        args.update(changes)
        return create_owned_profile(**args)

    def test_modern_cli_and_owned_destination(self):
        destination = self.create()
        self.assertEqual(destination, self.work / 'avd' / (NAME + '.avd'))
        argv, kwargs = self.calls[0]
        self.assertEqual(argv[-3:], ['emulator', 'create', 'Medium_Phone_API_37'])
        self.assertTrue(kwargs['check'])
        self.assertNotIn('avdmanager', argv[0])
        self.assertEqual({p.name for p in destination.iterdir()}, {'config.ini'})
        config = (destination / 'config.ini').read_text()
        self.assertIn('hw.cpu.arch=x86_64\n', config)
        self.assertIn('hw.mainKeys=no\n', config)
        self.assertNotIn('/foreign', config)
        self.assertEqual(list(self.work.glob('android17-profile-*')), [])
        self.assertEqual(os.environ.get('ANDROID_AVD_HOME'), self.environment_home)

    def test_both_cases_pin_distinct_installed_images(self):
        image = IMAGE.replace('google_apis;', 'google_apis_ps16k;')
        folder = self.sdk.joinpath(*image.split(';'))
        folder.mkdir(parents=True)
        (folder / 'system.img').write_bytes(b'synthetic')
        destination = self.create(image=image)
        config = (destination / 'config.ini').read_text()
        self.assertIn('tag.id=google_apis_ps16k\n', config)
        self.assertIn(str(folder), config)

    def test_foreign_or_old_image_stops_before_cli(self):
        for image in ('system-images;android-36;google_apis;x86_64', '../foreign', IMAGE + ';extra'):
            with self.subTest(image=image), self.assertRaises(ValueError):
                self.create(image=image)
        self.assertEqual(self.calls, [])

    def test_invalid_name_stops_before_cli(self):
        for name in ('../device', 'personal-phone', NAME + '\n'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.create(name=name)
        self.assertEqual(self.calls, [])

    def test_existing_owned_home_is_not_overwritten(self):
        home = self.work / 'avd'
        home.mkdir()
        existing = home / 'keep.ini'
        existing.write_text('must survive')
        with self.assertRaises(ValueError):
            self.create()
        self.assertEqual(existing.read_text(), 'must survive')
        self.assertEqual(self.calls, [])

    def test_missing_image_is_not_downloaded_implicitly(self):
        self.sdk.joinpath(*IMAGE.split(';'), 'system.img').unlink()
        with self.assertRaises(ValueError):
            self.create()
        self.assertEqual(self.calls, [])

    def test_cli_failure_is_not_success(self):
        def failed(argv, **kwargs):
            raise subprocess.CalledProcessError(1, argv)
        with self.assertRaises(subprocess.CalledProcessError):
            self.create(run=failed)
        self.assertFalse((self.work / 'avd' / (NAME + '.avd')).exists())

    def test_missing_or_ambiguous_created_profile_rejected(self):
        def missing(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, '')
        with self.assertRaises(ValueError):
            self.create(run=missing)
        def ambiguous(argv, **kwargs):
            self.fake_cli(argv, **kwargs)
            (Path(kwargs['env']['ANDROID_AVD_HOME']) / 'extra.avd').mkdir()
        with self.assertRaises(ValueError):
            self.create(run=ambiguous)

    def test_duplicate_properties_are_not_last_value_wins(self):
        def duplicate(argv, **kwargs):
            self.fake_cli(argv, **kwargs)
            path = next(Path(kwargs['env']['ANDROID_AVD_HOME']).glob('*.avd')) / 'config.ini'
            path.write_text('hw.cpu.arch=x86_64\nhw.cpu.arch=arm64\n')
        with self.assertRaises(ValueError):
            self.create(run=duplicate)

    def test_oversized_config_is_rejected(self):
        def oversized(argv, **kwargs):
            self.fake_cli(argv, **kwargs)
            path = next(Path(kwargs['env']['ANDROID_AVD_HOME']).glob('*.avd')) / 'config.ini'
            path.write_bytes(b'X' * 65537)
        with self.assertRaises(ValueError):
            self.create(run=oversized)


if __name__ == '__main__':
    unittest.main()
