"""Keep the boot gate aligned with the executable runtime matrix, not a copy."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import emulator_boot_readiness as readiness
from backend.android_runtime_contract import MIN_SDK, RUNTIME_PROFILES
from test_emulator_boot_readiness import Device


class BootRuntimeContractTests(unittest.TestCase):
    def test_all_obsolete_apis_rejected_before_any_device_access(self):
        for api in range(MIN_SDK):
            device = Device()
            session = readiness.prepared_emulator_session(device, device.name, api)
            with self.subTest(api=api), self.assertRaises(ValueError):
                session.__enter__()
            self.assertEqual(device.calls, [])

    def test_noninteger_or_unconfigured_future_api_is_not_coerced(self):
        future = max(profile.api for profile in RUNTIME_PROFILES) + 1
        for api in (True, False, str(MIN_SDK), float(MIN_SDK), None, future):
            device = Device()
            session = readiness.prepared_emulator_session(device, device.name, api)
            with self.subTest(api=repr(api)), self.assertRaises(ValueError):
                session.__enter__()
            self.assertEqual(device.calls, [])

    def test_current_api_requires_measured_matching_guest(self):
        for reported in (str(MIN_SDK - 1), str(MIN_SDK + 1), "", "unknown"):
            device = Device()
            device.api = reported
            session = readiness.prepared_emulator_session(device, device.name, MIN_SDK)
            with self.subTest(reported=reported), self.assertRaises(ValueError):
                session.__enter__()
            self.assertEqual([args for args, _ in device.calls], [
                ("emu", "avd", "name"), ("shell", "getprop", "ro.build.version.sdk"),
            ])

    def test_empty_runtime_contract_cannot_authorize_setup(self):
        device = Device()
        session = readiness.prepared_emulator_session(device, device.name, MIN_SDK)
        with patch.object(readiness, "RUNTIME_PROFILES", ()):
            with self.assertRaises(ValueError):
                session.__enter__()
        self.assertEqual(device.calls, [])

    def test_import_from_scripts_directory_without_repo_working_directory(self):
        scripts = str(Path(__file__).resolve().parents[1])
        code = ("import sys; sys.path.insert(0, sys.argv[1]); "
                "import emulator_boot_readiness as module; "
                "from backend.android_runtime_contract import RUNTIME_PROFILES; "
                "assert module.RUNTIME_PROFILES is RUNTIME_PROFILES")
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-I", "-c", code, scripts],
                                    cwd=directory, capture_output=True, text=True,
                                    timeout=15, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
