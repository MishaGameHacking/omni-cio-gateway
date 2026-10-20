"""Platform-policy unit tests; no emulator or APK is implied by these fixtures."""
import unittest
from backend.android_platform import (
    BUILD_TOOLS, COMPILE_ANDROID_API, MIN_ANDROID_API, RUNTIME_TARGETS,
    SDK_PLATFORM, TARGET_ANDROID_API, runtime_target, supported_client_api,
)


class AndroidPlatformTests(unittest.TestCase):
    def test_one_baseline(self):
        self.assertEqual((MIN_ANDROID_API, COMPILE_ANDROID_API, TARGET_ANDROID_API), (37, 37, 37))
        self.assertEqual(SDK_PLATFORM, 'android-37.0')
        self.assertEqual(BUILD_TOOLS, '37.0.0')

    def test_independent_cases_on_same_api(self):
        self.assertEqual({t.api for t in RUNTIME_TARGETS}, {37})
        self.assertEqual({t.key for t in RUNTIME_TARGETS}, {'37-4k', '37-16k'})
        self.assertEqual(len({t.report_directory for t in RUNTIME_TARGETS}), 2)
        self.assertEqual(len({t.system_image for t in RUNTIME_TARGETS}), 2)

    def test_exact_image_and_directory(self):
        target = runtime_target(37, 16384)
        self.assertEqual(target.system_image, 'system-images;android-37.0;google_apis_ps16k;x86_64')
        self.assertEqual(target.report_directory, 'install-api-37-16k')
        self.assertEqual(runtime_target(37, 4096).system_image,
                         'system-images;android-37.0;google_apis;x86_64')

    def test_unverified_runtime_api_is_not_accepted(self):
        for value in (None, True, 35, 36, 38, '37', 37.0, -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                runtime_target(value, 16384)

    def test_page_size_is_not_inferred_or_coerced(self):
        for value in (None, True, '16384', 16384.0, 8192, 65536, -4096):
            with self.subTest(value=value), self.assertRaises(ValueError):
                runtime_target(37, value)

    def test_client_eligibility_does_not_certify_runtime(self):
        self.assertTrue(supported_client_api(37))
        self.assertTrue(supported_client_api(38))
        for value in (None, True, 33, 35, 36, '37', 37.0, 101):
            with self.subTest(value=value):
                self.assertFalse(supported_client_api(value))


if __name__ == '__main__':
    unittest.main()
