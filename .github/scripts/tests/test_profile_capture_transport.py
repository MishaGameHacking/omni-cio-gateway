"""Unit fixtures verify screenshot transport and dialog waits, not native UI success."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import profile_ui_probe as ui


def png_bytes():
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    header = struct.pack('>IIBBBBB', 8, 8, 8, 2, 0, 0, 0)
    pixels = b''.join(b'\0' + bytes(range(row, row + 24)) for row in range(8))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b'')


class CaptureTransportTests(unittest.TestCase):
    def exercise_capture(self, payload, fail_at=None):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / '.github/scripts/profile_ui_probe.py'
            source.parent.mkdir(parents=True)
            source.write_text('# unit fixture', encoding='utf-8')
            calls = []
            failure = RuntimeError('synthetic transport loss')
            def command(*args):
                calls.append(args)
                if args[0] == fail_at:
                    raise failure
                if args[0] == 'pull' and payload is not None:
                    Path(args[-1]).write_bytes(payload)
                return ''
            probe = ui.ProfileProbe(Mock())
            with patch.object(ui, '__file__', str(source)), patch.object(probe, 'command', side_effect=command):
                destination = root / 'app/build/outputs/apk/preview/ui-screens/capture.png'
                if fail_at:
                    with self.assertRaises(RuntimeError) as raised:
                        probe.capture('capture')
                    self.assertIs(raised.exception, failure)
                    self.assertFalse(destination.exists())
                elif payload is None or not payload.endswith(b'\0\0\0\0IEND\xaeB`\x82'):
                    with self.assertRaises(AssertionError):
                        probe.capture('capture')
                    self.assertFalse(destination.exists())
                else:
                    probe.capture('capture')
                    self.assertEqual(destination.read_bytes(), payload)
            return calls

    def test_guest_screencap_and_pull_preserve_bytes(self):
        calls = self.exercise_capture(png_bytes())
        self.assertEqual(calls[0][:3], ('shell', 'screencap', '-p'))
        self.assertRegex(calls[0][3], r'^/sdcard/analyst-ui-[0-9a-f]{32}\.png$')
        self.assertEqual(calls[1][:2], ('pull', calls[0][3]))
        self.assertEqual(calls[2], ('shell', 'rm', '-f', calls[0][3]))
        self.assertFalse(any('emu' in call for call in calls))

    def test_missing_transfer_cannot_reuse_previous_picture(self):
        self.exercise_capture(None)

    def test_truncated_png_is_not_evidence(self):
        self.exercise_capture(png_bytes()[:-12])

    def test_transfer_error_is_not_a_success(self):
        self.exercise_capture(png_bytes(), fail_at='pull')

    def test_preflight_checks_dialogs_without_duplicate_capture(self):
        probe = ui.ProfileProbe(Mock())
        with patch.object(probe, 'open') as opened, patch.object(probe, 'dialogs') as dialogs, \
                patch.object(probe, 'section_scroll_reset') as reset:
            probe.profile_preflight()
        opened.assert_called_once_with()
        dialogs.assert_called_once_with(capture_evidence=False)
        reset.assert_called_once_with()

    def test_full_dialog_stage_still_requires_all_three_screenshots(self):
        probe = ui.ProfileProbe(Mock())
        version_tree = ET.fromstring('<hierarchy><node text="Версия 0.7.0" /></hierarchy>')
        with patch.object(probe, 'tap'), patch.object(probe, 'find'), \
                patch.object(probe, 'tap_visible'), patch.object(probe, 'horizontal_info'), \
                patch.object(probe, 'tap_profile_content'), patch.object(probe, 'tree', return_value=version_tree), \
                patch.object(probe, 'capture') as capture:
            probe.dialogs(capture_evidence=False)
            capture.assert_not_called()
            probe.dialogs()
            self.assertEqual([item.args[0] for item in capture.call_args_list],
                             ['security', 'info', 'about'])

    def test_dialog_wait_does_not_scroll_underlying_profile(self):
        probe = ui.ProfileProbe(Mock())
        empty = ET.fromstring('<hierarchy><node package="ru.omnicio.app.debug" resource-id="profile-content" scrollable="true" bounds="[0,100][320,600]"/></hierarchy>')
        ready = ET.fromstring('<hierarchy><node package="ru.omnicio.app.debug" text="Как в системе" bounds="[20,120][280,180]"/></hierarchy>')
        with patch.object(probe, 'tree', side_effect=[empty, ready]), patch.object(probe, 'command') as command, patch.object(ui.time, 'sleep'):
            probe.tap_visible('Как в системе')
        command.assert_called_once_with('shell', 'input', 'tap', '150', '150')

    def test_foreign_dialog_label_cannot_be_tapped(self):
        probe = ui.ProfileProbe(Mock())
        foreign = ET.fromstring('<hierarchy><node package="other.app" text="Как в системе" bounds="[20,120][280,180]"/></hierarchy>')
        with patch.object(probe, 'tree', return_value=foreign), patch.object(probe, 'command') as command, patch.object(ui.time, 'sleep'), patch.object(ui.time, 'monotonic', side_effect=[0, 0, 13]):
            with self.assertRaises(AssertionError):
                probe.tap_visible('Как в системе')
        command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
