"""Page size is measured independently for each supported current-OS profile."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kernel_page_size import measured_record, system_image, validate_record

DIGEST = 'a' * 64


class KernelPageSizeTests(unittest.TestCase):
    def test_both_page_sizes_on_same_api_are_real_measurements(self):
        for pages in (4096, 16384):
            record = measured_record(37, str(pages) + '\r\n', DIGEST, page_size_bytes=pages)
            validate_record(record, 37, page_size_bytes=pages)
            self.assertEqual(record['page_size_bytes'], pages)
            self.assertEqual(record['android_api'], 37)
            self.assertIn('android-37.0;', record['system_image'])

    def test_other_page_size_cannot_substitute_for_requested_profile(self):
        for requested, actual in ((4096, 16384), (16384, 4096)):
            output = str(actual)
            with self.assertRaises(ValueError):
                measured_record(37, output, DIGEST, page_size_bytes=requested)

    def test_unsupported_os_and_coercions_are_rejected(self):
        for api in (35, 36, 38, '37', True, 37.0):
            with self.subTest(api=api), self.assertRaises(ValueError):
                system_image(api)
        for pages in (0, 8192, '4096', True, 4096.0):
            with self.subTest(pages=pages), self.assertRaises(ValueError):
                system_image(37, pages)

    def test_distinct_profiles_have_distinct_official_image_ids(self):
        self.assertEqual(system_image(37, 4096), 'system-images;android-37.0;google_apis;x86_64')
        self.assertEqual(system_image(37, 16384), 'system-images;android-37.0;google_apis_ps16k;x86_64')

    def test_fields_cannot_be_missing_or_tampered(self):
        for pages in (4096, 16384):
            original = measured_record(37, str(pages), DIGEST, page_size_bytes=pages)
            for key in original:
                missing = {k: v for k, v in original.items() if k != key}
                wrong = dict(original, **{key: None})
                with self.subTest(page=pages, key=key):
                    with self.assertRaises(ValueError):
                        validate_record(missing, 37, page_size_bytes=pages)
                    with self.assertRaises(ValueError):
                        validate_record(wrong, 37, page_size_bytes=pages)

    def test_numeric_types_and_success_flag_are_not_coerced(self):
        for key, value in (('success', 1), ('android_api', 37.0), ('page_size_bytes', 4096.0)):
            original = measured_record(37, '4096', DIGEST)
            original[key] = value
            with self.assertRaises(ValueError):
                validate_record(original, 37)

    def test_bad_guest_output_is_not_a_valid_observation(self):
        for output in (None, 4096, '4096\n16384', 'page_size_bytes=4096', '', '0'):
            with self.assertRaises(ValueError):
                measured_record(37, output, DIGEST)

    def test_bad_artifact_digest_is_rejected(self):
        for digest in (None, '', 'A' * 64, '../artifact'):
            with self.assertRaises(ValueError):
                measured_record(37, '4096', digest)


if __name__ == '__main__':
    unittest.main()
