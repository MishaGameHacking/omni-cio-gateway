import hashlib
from pathlib import Path
import struct
import sys
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_apk import InvalidAPK, check_dex, check_elf64, check_manifest, manifest_flag

BADGING = (
    "package: name='ru.omnicio.app.debug' versionCode='20' versionName='0.4.2-preview'\n"
    "sdkVersion:'35'\ntargetSdkVersion:'36'"
)


def dex(version=b"039"):
    data = bytearray(112)
    data[:8] = b"dex\n" + version + b"\0"
    struct.pack_into("<III", data, 32, len(data), 112, 0x12345678)
    data[12:32] = hashlib.sha1(data[32:], usedforsecurity=False).digest()
    struct.pack_into("<I", data, 8, zlib.adler32(data[12:]))
    return bytes(data)


def elf(alignment=16384):
    data = bytearray(120)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<Q", data, 32, 64)
    struct.pack_into("<HH", data, 54, 56, 1)
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 0, 0, 0, 120, 120, alignment)
    return bytes(data)


class ArtifactChecks(unittest.TestCase):
    def test_dex_integrity(self):
        self.assertEqual(check_dex(dex()), "039")

    def test_dex_android_10_format_allowed(self):
        self.assertEqual(check_dex(dex(b"040")), "040")

    def test_experimental_container_rejected(self):
        data = dex(b"041")
        with self.assertRaises(InvalidAPK):
            check_dex(data)

    def test_corrupt_dex_rejected(self):
        data = bytearray(dex())
        data[-1] = 1
        with self.assertRaises(InvalidAPK):
            check_dex(data)

    def test_truncated_dex_rejected(self):
        with self.assertRaises(InvalidAPK):
            check_dex(b"dex")

    def test_elf_16k_allowed(self):
        check_elf64(elf())

    def test_elf_4k_rejected(self):
        data = elf(4096)
        with self.assertRaises(InvalidAPK):
            check_elf64(data)

    def test_manifest_boolean(self):
        self.assertTrue(manifest_flag("A: android:testOnly(0x01010272)=(type 0x12)0xffffffff", "testOnly"))
        self.assertFalse(manifest_flag("A: android:testOnly(0x01010272)=(type 0x12)0x0", "testOnly"))
        self.assertFalse(manifest_flag("", "testOnly"))

    def test_distribution_manifest(self):
        self.assertEqual(check_manifest(BADGING, "", 20, True)["version_code"], 20)

    def test_testonly_distribution_rejected(self):
        with self.assertRaises(InvalidAPK):
            check_manifest(BADGING, "A: android:testOnly(0x01010272)=(type 0x12)0xffffffff", 20, True)

    def test_debuggable_distribution_rejected(self):
        with self.assertRaises(InvalidAPK):
            check_manifest(BADGING, "A: android:debuggable(0x0101000f)=(type 0x12)0xffffffff", 20, True)

    def test_wrong_package_rejected(self):
        badging = BADGING.replace("ru.omnicio.app.debug", "other")
        with self.assertRaises(InvalidAPK):
            check_manifest(badging, "", 20, True)


if __name__ == "__main__":
    unittest.main()
