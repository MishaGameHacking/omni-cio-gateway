"""Only parse/restore guards; actual Android event delivery is a separate CI gate."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("spatial_policy_probe", SCRIPTS / "spatial_policy_probe.py")
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


class SpatialPolicyGuardTests(unittest.TestCase):
    def test_only_one_known_enabled_navigation_overlay_can_be_restored(self):
        actual = "[x] com.android.internal.systemui.navbar.threebutton\n[ ] com.android.internal.systemui.navbar.gestural\n"
        self.assertEqual("com.android.internal.systemui.navbar.threebutton", policy.active_navigation_overlay(actual))
        for text in ("", actual + "[x] com.android.internal.systemui.navbar.gestural\n",
                     "[x] com.android.internal.systemui.navbar.custom\n", "[ ] com.android.internal.systemui.navbar.threebutton\n"):
            with self.subTest(text=text), self.assertRaises(AssertionError):
                policy.active_navigation_overlay(text)

    def test_scale_restore_never_forwards_an_untrusted_shell_argument(self):
        for original in ("null", "1; reboot", "$(command)", "NaN", "1000"):
            probe = Mock()
            policy._restore_animator_scale(probe, original)
            probe.command.assert_called_once_with("shell", "settings", "delete", "global", "animator_duration_scale")
        probe = Mock()
        policy._restore_animator_scale(probe, "0.5")
        probe.command.assert_called_once_with("shell", "settings", "put", "global", "animator_duration_scale", "0.5")


if __name__ == "__main__":
    unittest.main()
