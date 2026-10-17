"""Synthetic parser cases; none of these tests claims to boot an emulator."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kernel_page_size import measured_record, system_image, validate_record


class KernelPageSizeTests(unittest.TestCase):
    def test_actual_output_is_required_for_each_fixed_matrix_entry(self):
        for api, size in ((35, 16384), (36, 4096)):
            row = measured_record(api, f"{size}\r\n", "a" * 64)
            validate_record(row, api)
            self.assertEqual(size, row["page_size_bytes"])
            self.assertEqual("getconf PAGE_SIZE", row["command"])
        self.assertIn("google_apis_ps16k", system_image(35))
        self.assertNotIn("ps16k", system_image(36))

    def test_4kb_cannot_masquerade_as_android15_runtime_16kb(self):
        for value in ("4096", "", "16384\n4096", "16384 bytes", "16384.0", "true"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                measured_record(35, value, "a" * 64)
        for api in (34, 37, "35", True, 35.0):
            with self.subTest(api=api), self.assertRaises(ValueError):
                system_image(api)

    def test_every_identity_and_measurement_field_is_checked(self):
        row = measured_record(35, "16384", "a" * 64)
        for field, value in (("android_api", 36), ("android_api", "35"),
                             ("abi", "arm64-v8a"), ("system_image", system_image(36)),
                             ("page_size_bytes", "16384"), ("page_size_bytes", 4096),
                             ("command", "ELF alignment"), ("success", 1),
                             ("apk_sha256", "not-a-digest")):
            altered = deepcopy(row)
            altered[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_record(altered, 35)
        for field in row:
            altered = deepcopy(row)
            del altered[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                validate_record(altered, 35)


if __name__ == "__main__":
    unittest.main()
