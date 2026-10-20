"""Synthetic parser cases; these tests do not claim to boot an emulator."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kernel_page_size import measured_record, system_image, validate_record

DIGEST = "a" * 64


class KernelPageSizeTests(unittest.TestCase):
    def test_actual_output_is_required_for_each_fixed_matrix_entry(self):
        for size in (16384, 4096):
            row = measured_record(37, f"{size}\r\n", DIGEST, page_size_bytes=size)
            validate_record(row, 37, page_size_bytes=size)
            self.assertEqual(size, row["page_size_bytes"])
            self.assertEqual("getconf PAGE_SIZE", row["command"])
        self.assertIn("google_apis_ps16k", system_image(37, 16384))
        self.assertNotIn("ps16k", system_image(37, 4096))

    def test_4kb_cannot_masquerade_as_runtime_16kb(self):
        for value in ("4096", "", "16384\n4096", "16384 bytes", "16384.0", "true"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                measured_record(37, value, DIGEST, page_size_bytes=16384)
        for api in (34, 35, 36, 38, "37", True, 37.0):
            with self.subTest(api=api), self.assertRaises(ValueError):
                system_image(api, 16384)
        for size in (True, 16384.0, "16384", 8192, None):
            with self.subTest(size=size), self.assertRaises(ValueError):
                system_image(37, size)

    def test_every_identity_and_measurement_field_is_checked(self):
        row = measured_record(37, "16384", DIGEST, page_size_bytes=16384)
        alternate_image = system_image(37, 4096)
        for field, value in (("android_api", 36), ("android_api", "37"),
                             ("runtime_case", "37-4k"), ("abi", "arm64-v8a"),
                             ("system_image", alternate_image), ("page_size_bytes", "16384"),
                             ("page_size_bytes", 4096), ("command", "ELF alignment"),
                             ("success", 1), ("apk_sha256", "not-a-digest")):
            altered = deepcopy(row)
            altered[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_record(altered, 37, page_size_bytes=16384)
        for field in row:
            altered = deepcopy(row)
            del altered[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                validate_record(altered, 37, page_size_bytes=16384)


if __name__ == "__main__":
    unittest.main()
