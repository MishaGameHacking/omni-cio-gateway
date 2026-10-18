"""Offline graphics evidence regressions; these do not claim an emulator pass."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emulator_graphics import (
    MAX_LOG_CHARACTERS, parse_filament_renderer, read_filament_renderer,
    require_guest_angle, snapshot_system_graphics,
)


UID, PID = "10207", "3014"
ANGLE = "ANGLE (Google, Vulkan 1.3.0 (llvmpipe (LLVM 18.1.8, 256 bits)), Mesa driver)"
LEGACY = "Android Emulator OpenGL ES Translator (Google SwiftShader)"


def header(renderer=ANGLE, *, pid=PID, version="OpenGL ES 3.1 ANGLE (synthetic)"):
    return (f"10-18 05:23:31.044  {pid}  3127 I Filament: "
            f"[Google (Mesa)], [{renderer}], [{version}], [OpenGL ES GLSL ES 3.10]\n")


def observed(text):
    return parse_filament_renderer(text, uid=UID, pid=PID)


class EmulatorGraphicsTests(unittest.TestCase):
    def test_complete_context_preserves_angle_commas_and_actual_versions(self):
        row = observed(header())
        require_guest_angle(row)
        self.assertEqual(row, {
            "source": "candidate-filament-logcat", "uid": 10207, "pid": 3014,
            "header_count": 1, "vendor": "Google (Mesa)", "renderer": ANGLE,
            "version": "OpenGL ES 3.1 ANGLE (synthetic)",
            "shading_language_version": "OpenGL ES GLSL ES 3.10",
        })

    def test_recreated_engines_can_repeat_the_same_complete_context(self):
        row = observed(header() + "unrelated engine message\n" + header())
        require_guest_angle(row)
        self.assertEqual(row["header_count"], 2)

    def test_actual_p7_legacy_compiler_is_retained_but_cannot_pass(self):
        row = observed(header(LEGACY, version="OpenGL ES 3.0 (OpenGL ES 3.0 SwiftShader 4.0.0.1)"))
        self.assertEqual(row["renderer"], LEGACY)
        with self.assertRaisesRegex(ValueError, "ANGLE-on-Vulkan"):
            require_guest_angle(row)

    def test_angle_on_another_api_or_gles_below_three_cannot_pass(self):
        for renderer, version in (
            ("ANGLE (Google, Direct3D11 renderer)", "OpenGL ES 3.1"),
            ("ANGLE (Google, OpenGL renderer)", "OpenGL ES 3.1"),
            ("Vulkan (not an ANGLE context)", "OpenGL ES 2.0"),
            (ANGLE, "OpenGL ES 2.0"),
            (ANGLE, "OpenGL ES unknown"),
        ):
            prepared_argument_1 = observed(header(renderer, version=version))
            with self.subTest(renderer=renderer, version=version), self.assertRaises(ValueError):
                require_guest_angle(prepared_argument_1)

    def test_requested_flags_system_output_or_incomplete_headers_are_not_contexts(self):
        for text in (
            "", "-gpu lavapipe -feature Vulkan,GuestAngle",
            "GLES: Google, " + ANGLE + ", OpenGL ES 3.1",
            header().replace("I Filament:", "I GraphicsEnvironment:"),
            header().replace("[Google (Mesa)]", "[ ]"),
            header().replace(", [OpenGL ES GLSL ES 3.10]", ""),
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                observed(text)
        for incomplete in ({}, {"renderer": ANGLE}, {"renderer": None, "version": "OpenGL ES 3.1"}):
            with self.subTest(incomplete=incomplete), self.assertRaises(ValueError):
                require_guest_angle(incomplete)

    def test_previous_launch_pid_cannot_supply_a_new_launch_record(self):
        for text in (header(pid="2999"), header() + header(pid="2999")):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "another process"):
                observed(text)

    def test_conflicting_driver_headers_in_one_process_fail_closed(self):
        prepared_argument_1 = header() + header(LEGACY)
        with self.assertRaisesRegex(ValueError, "conflicting"):
            observed(prepared_argument_1)

    def test_oversized_log_cannot_hide_conflicting_evidence_behind_truncation(self):
        prepared_argument_1 = header() + "x" * MAX_LOG_CHARACTERS + header(LEGACY)
        with self.assertRaisesRegex(ValueError, "bounded"):
            observed(prepared_argument_1)

    def test_context_read_uses_both_current_uid_and_fresh_pid_without_clearing_logs(self):
        device = Mock(return_value=subprocess.CompletedProcess([], 0, header(), ""))
        row = read_filament_renderer(device, uid=UID, pid=PID + "\n")
        require_guest_angle(row)
        device.assert_called_once_with(
            "logcat", "-d", "-b", "main", "-v", "threadtime",
            "--uid=" + UID, "--pid=" + PID, "Filament:I", "*:S", timeout=10,
        )

    def test_missing_ambiguous_or_injected_identity_never_reaches_adb(self):
        for uid, pid in (("", PID), ("9999", PID), (UID, ""), (UID, "3014 2999"),
                         (UID, "0"), (UID, "2147483648"), (UID, "3014 --uid=0"),
                         (UID + " --pid=1", PID), (None, PID), (UID, None)):
            device = Mock()
            with self.subTest(uid=uid, pid=pid), self.assertRaises(ValueError):
                read_filament_renderer(device, uid=uid, pid=pid)
            device.assert_not_called()

    def test_failed_context_command_cannot_pass_from_its_stdout(self):
        device = Mock(return_value=subprocess.CompletedProcess([], 1, header(), "failed"))
        with self.assertRaisesRegex(RuntimeError, "Could not read"):
            read_filament_renderer(device, uid=UID, pid=PID)
        device.assert_called_once()

    def test_context_timeout_is_propagated_without_retry_or_success(self):
        failure = subprocess.TimeoutExpired("logcat", 10)
        device = Mock(side_effect=failure)
        with self.assertRaises(subprocess.TimeoutExpired) as raised:
            read_filament_renderer(device, uid=UID, pid=PID)
        self.assertIs(raised.exception, failure)
        device.assert_called_once()

    def test_system_skia_vulkan_is_bounded_separate_observation_not_app_proof(self):
        device = Mock(side_effect=[
            subprocess.CompletedProcess([], 0, value, "")
            for value in ("angle\n", "ranchu\n", "skiavk\n", "skiavk\n",
                          "Unrelated surface\nRenderEngine: SkiaVk\nVulkan: system device\n" + "Skia " * 1000)
        ])
        system = snapshot_system_graphics(device)
        self.assertEqual(system["properties"]["ro.hardware.egl"]["value"], "angle")
        self.assertEqual(system["system_compositor"]["graphics_lines"][:2],
                         ["RenderEngine: SkiaVk", "Vulkan: system device"])
        self.assertTrue(all(len(line) <= 512 for line in system["system_compositor"]["graphics_lines"]))
        self.assertEqual(device.call_count, 5)
        self.assertTrue(all(call.kwargs["timeout"] == 10 for call in device.call_args_list))
        with self.assertRaises(ValueError):
            require_guest_angle(system)

    def test_missing_system_diagnostics_still_cannot_substitute_for_app_evidence(self):
        device = Mock(side_effect=OSError("unavailable"))
        system = snapshot_system_graphics(device)
        self.assertEqual(device.call_count, 5)
        self.assertEqual(system["system_compositor"]["error_type"], "OSError")
        self.assertEqual(system["properties"]["ro.hardware.egl"]["error_type"], "OSError")
        with self.assertRaises(ValueError):
            require_guest_angle(system)


if __name__ == "__main__":
    unittest.main()
