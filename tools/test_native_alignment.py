"""Synthetic byte fixtures test the checker; they do not prove device support."""
from __future__ import annotations

from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

from check_native_alignment import NativeAlignmentError, check_elf, inspect_native_archive, trusted_artifact_path, write_report


def elf(*, bits=64, alignment=16384, address=0, relro_size=None, memory_size=16384):
    header_size, entry_size = (64, 56) if bits == 64 else (52, 32)
    count = 1 if relro_size is None else 2
    data = bytearray(header_size + count * entry_size)
    data[:7] = b"\x7fELF" + bytes((2 if bits == 64 else 1, 1, 1))
    if bits == 64:
        struct.pack_into("<Q", data, 32, header_size)
        struct.pack_into("<HH", data, 54, entry_size, count)
        struct.pack_into("<IIQQQQQQ", data, header_size, 1, 6, 0, address, 0,
                         len(data), memory_size, alignment)
        if relro_size is not None:
            struct.pack_into("<IIQQQQQQ", data, header_size + entry_size,
                             0x6474E552, 4, 0, address, 0, len(data), relro_size, 1)
    else:
        struct.pack_into("<I", data, 28, header_size)
        struct.pack_into("<HH", data, 42, entry_size, count)
        struct.pack_into("<IIIIIIII", data, header_size, 1, 0, address, 0,
                         len(data), memory_size, 6, alignment)
        if relro_size is not None:
            struct.pack_into("<IIIIIIII", data, header_size + entry_size,
                             0x6474E552, 0, address, 0, len(data), relro_size, 4, 1)
    return bytes(data)


class NativeAlignmentTests(unittest.TestCase):
    def test_cli_reads_only_regular_files_inside_checkout_build_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            build = root / "app/build/outputs/apk"
            build.mkdir(parents=True)
            artifact = build / "candidate.so"
            artifact.write_bytes(elf())
            checked = trusted_artifact_path(Path("app/build/outputs/apk/candidate.so"), root)
            # Windows temporary roots can use 8.3 aliases; the checker deliberately
            # returns the canonical long path after all traversal/link checks.
            self.assertEqual(checked, artifact.resolve(strict=True))
            self.assertTrue(checked.samefile(artifact))
            outside = Path(directory) / "outside.so"
            outside.write_bytes(elf())
            for path in (outside, Path("app/build/outputs/apk/../apk/candidate.so"), root / "source.so"):
                with self.subTest(path=path), self.assertRaises(NativeAlignmentError):
                    trusted_artifact_path(path, root)

    def test_cli_rejects_file_and_parent_symlinks_and_output_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            build = root / "app/build"
            build.mkdir(parents=True)
            outside = Path(directory) / "outside"
            outside.mkdir()
            (outside / "secret.so").write_bytes(elf())
            link = build / "redirect"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError as error:
                # Windows can lack symlink creation privilege. Test the same
                # decision through the real pathlib query without skipping gates.
                from unittest.mock import patch
                with patch.object(Path, "is_symlink", return_value=True):
                    with self.assertRaises(NativeAlignmentError):
                        trusted_artifact_path(build / "secret.so", root)
                    with self.assertRaises(NativeAlignmentError):
                        write_report("{}\n", root)
                self.assertIsInstance(error, OSError)
            else:
                with self.assertRaises(NativeAlignmentError):
                    trusted_artifact_path(link / "secret.so", root)
                direct = build / "linked.so"
                direct.symlink_to(outside / "secret.so")
                with self.assertRaises(NativeAlignmentError):
                    trusted_artifact_path(direct, root)
                (build / "reports").symlink_to(outside, target_is_directory=True)
                with self.assertRaises(NativeAlignmentError):
                    write_report("{}\n", root)
                self.assertFalse((outside / "native-alignment.json").exists())

    def test_cli_report_has_one_fixed_location_and_atomic_regular_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = write_report('{"first":true}\n', root)
            second = write_report('{"second":true}\n', root)
            expected = (root / "app/build/reports/native-alignment.json").resolve(strict=True)
            self.assertEqual(first, expected)
            self.assertTrue(first.samefile(expected))
            self.assertEqual(first, second)
            self.assertEqual(second.read_text(), '{"second":true}\n')
            self.assertEqual(list(second.parent.glob(".native-alignment-*")), [])

    def test_real_elf_layouts_on_both_classes(self):
        for bits in (32, 64):
            self.assertEqual(check_elf(elf(bits=bits))["bits"], bits)

    def test_4kb_load_and_wrong_address_are_rejected(self):
        for data in (elf(alignment=4096), elf(address=4096)):
            with self.assertRaises(NativeAlignmentError):
                check_elf(data)

    def test_truncated_header_table_and_payload_are_rejected(self):
        original = elf()
        for data in (b"ELF", original[:60], original[:-1]):
            with self.assertRaises(NativeAlignmentError):
                check_elf(data)
        data = bytearray(original)
        struct.pack_into("<Q", data, 64 + 32, len(data) + 100)
        with self.assertRaises(NativeAlignmentError):
            check_elf(bytes(data))

    def test_relro_with_own_load_is_valid_even_if_end_is_not_page_aligned(self):
        result = check_elf(elf(relro_size=4096, memory_size=4096))
        self.assertEqual(result["relro_segments"][0]["layout"], "own_load_segment")

    def test_relro_sharing_a_load_requires_safe_page_boundary(self):
        self.assertTrue(check_elf(elf(relro_size=16384, memory_size=32768))["relro_16kb"])
        with self.assertRaisesRegex(NativeAlignmentError, "overlaps writable"):
            check_elf(elf(relro_size=4096, memory_size=32768))

    def test_relro_alignment_padding_may_extend_past_load_payload_but_not_its_page(self):
        self.assertTrue(check_elf(elf(relro_size=4096, memory_size=3072))["relro_16kb"])
        with self.assertRaisesRegex(NativeAlignmentError, "outside its LOAD"):
            check_elf(elf(relro_size=32768, memory_size=3072))

    def test_local_zip_data_offset_and_uncompressed_requirement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.apk"
            name = "lib/arm64-v8a/libtest.so"
            for aligned in (False, True):
                info = zipfile.ZipInfo(name)
                if aligned:
                    padding = (-(30 + len(name) + 4)) % 16384
                    info.extra = struct.pack("<HH", 0xBEEF, padding) + bytes(padding)
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr(info, elf())
                if aligned:
                    result = inspect_native_archive(path, require_stored=True)
                    self.assertTrue(result["zip_16kb"])
                    self.assertEqual(result["libraries"][0]["zip_data_offset"], 16384)
                else:
                    with self.assertRaisesRegex(NativeAlignmentError, "ZIP data"):
                        inspect_native_archive(path, require_stored=True)
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(name, elf(), compress_type=zipfile.ZIP_DEFLATED)
            with self.assertRaisesRegex(NativeAlignmentError, "uncompressed"):
                inspect_native_archive(path, require_stored=True)
            self.assertFalse(inspect_native_archive(path)["zip_16kb"])

    def test_aar_compression_is_not_an_apk_alignment_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dependency.aar"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("jni/arm64-v8a/libtest.so", elf(), compress_type=zipfile.ZIP_DEFLATED)
            result = inspect_native_archive(path, require_stored=True)
            self.assertTrue(result["elf_16kb"])
            self.assertIsNone(result["zip_16kb"])


if __name__ == "__main__":
    unittest.main()
