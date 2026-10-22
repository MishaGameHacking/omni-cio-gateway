"""Real cache-layout and process-boundary tests; no JDK download or signing keys."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_cached_jdk as jdk


class CachedJdkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "tool cache with spaces"
        self.root.mkdir()
        self.home = self.cache("17.0.20-101")
        self.environment_file = self.root / "environment"
        self.path_file = self.root / "path"
        self.environment_file.write_text("PRESERVED=yes\n", encoding="utf-8")
        self.path_file.write_text("", encoding="utf-8")
        self.env = {"RUNNER_TOOL_CACHE": str(self.root),
                    "GITHUB_ENV": str(self.environment_file), "GITHUB_PATH": str(self.path_file)}

    def cache(self, version, *, complete=True):
        home = self.root / jdk.CACHE_FAMILY / version / "x64"
        (home / "bin").mkdir(parents=True)
        for name in ("java.exe", "javac.exe", "keytool.exe"):
            (home / "bin" / name).write_bytes(b"fixture executable")
        if complete:
            home.with_suffix(".complete").write_bytes(b"")
        return home

    def properties(self, **changes):
        values = {"java.specification.version": "17", "java.vendor": "Eclipse Adoptium",
                  "java.runtime.version": "17.0.20.1+1", "java.home": str(self.home),
                  "os.arch": "amd64", "sun.arch.data.model": "64"}
        values.update(changes)
        return "Property settings:\n" + "\n".join(f"    {key} = {value}" for key, value in values.items())

    def run_java(self, command, **_):
        output = "javac 17.0.20.1\n" if command[0].endswith("javac.exe") else self.properties()
        return subprocess.CompletedProcess(command, 0, output.encode())

    def test_selects_latest_completed_numeric_stable_cache(self):
        self.cache("17.0.9-999")
        self.cache("17.0.20-99")
        self.cache("17.0.21-1", complete=False)
        self.cache("17.0.22-1-ea")
        self.cache("21.0.2-5")
        self.assertEqual(jdk.discover(str(self.root)), self.home)

    def test_exports_only_after_actual_runtime_and_compiler_verify(self):
        with patch.object(jdk.subprocess, "run", side_effect=self.run_java) as run:
            result = jdk.configure(self.env)
        self.assertEqual(result, "17.0.20.1+1")
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0].args[0],
                         [str(self.home / "bin/java.exe"), "-XshowSettings:properties", "-version"])
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["timeout"], 30)
            self.assertEqual(call.kwargs["env"], self.env)
            self.assertNotIn("shell", call.kwargs)
        self.assertEqual(self.environment_file.read_text(),
                         f"PRESERVED=yes\nJAVA_HOME={self.home}\nJAVA_HOME_17_X64={self.home}\n")
        self.assertEqual(self.path_file.read_text(), f"{self.home / 'bin'}\n")

    def test_missing_cache_never_uses_java_home_or_path(self):
        env = dict(self.env, RUNNER_TOOL_CACHE="", JAVA_HOME=str(self.home), PATH=str(self.home / "bin"))
        with patch.object(jdk.subprocess, "run") as run:
            with self.assertRaises(jdk.CachedJdkError):
                jdk.configure(env)
        run.assert_not_called()
        self.assertEqual(self.environment_file.read_text(), "PRESERVED=yes\n")

    def test_incomplete_cache_is_not_runnable(self):
        self.home.with_suffix(".complete").unlink()
        with self.assertRaises(jdk.CachedJdkError):
            jdk.discover(str(self.root))

    def test_invalid_root_is_rejected(self):
        for root in ("", "relative", str(self.root) + "\nINJECTED=yes", str(self.environment_file)):
            with self.subTest(root=root), self.assertRaises(jdk.CachedJdkError):
                jdk.discover(root)

    def test_corrupt_latest_installation_does_not_fall_back(self):
        self.cache("17.0.19-5")
        (self.home / "bin/javac.exe").write_bytes(b"")
        with self.assertRaises(jdk.CachedJdkError):
            jdk.discover(str(self.root))

    def test_jre_cannot_replace_a_jdk(self):
        (self.home / "bin/javac.exe").unlink()
        with self.assertRaises(FileNotFoundError):
            jdk.discover(str(self.root))

    def make_link(self, link, target):
        try:
            link.symlink_to(target, target_is_directory=target.is_dir())
        except OSError:
            self.skipTest("Host does not permit symlink creation")

    def test_linked_executable_is_not_run(self):
        executable = self.home / "bin/java.exe"
        executable.unlink()
        self.make_link(executable, self.environment_file)
        with patch.object(jdk.subprocess, "run") as run:
            with self.assertRaises(jdk.CachedJdkError):
                jdk.configure(self.env)
        run.assert_not_called()

    def test_linked_cache_root_is_rejected(self):
        link = self.root.parent / "linked cache"
        self.make_link(link, self.root)
        with self.assertRaises(jdk.CachedJdkError):
            jdk.discover(str(link))

    def test_marker_must_be_a_regular_file(self):
        marker = self.home.with_suffix(".complete")
        marker.unlink()
        marker.mkdir()
        with self.assertRaises(jdk.CachedJdkError):
            jdk.discover(str(self.root))

    def test_wrong_runtime_properties_fail_without_exports(self):
        cases = ({"java.specification.version": "21"}, {"java.vendor": "Other vendor"},
                 {"os.arch": "aarch64"}, {"sun.arch.data.model": "32"},
                 {"java.home": str(self.root)}, {"java.runtime.version": "17-ea+1"},
                 {"java.runtime.version": "17.0.20+1-ea"})
        for changes in cases:
            result = subprocess.CompletedProcess([], 0, self.properties(**changes).encode())
            with self.subTest(changes=changes), patch.object(jdk.subprocess, "run", return_value=result):
                with self.assertRaises(jdk.CachedJdkError):
                    jdk.configure(self.env)
            self.assertEqual(self.environment_file.read_text(), "PRESERVED=yes\n")
            self.assertEqual(self.path_file.read_text(), "")

    def test_duplicate_runtime_property_is_not_accepted(self):
        output = (self.properties() + "\njava.specification.version = 17\n").encode()
        result = subprocess.CompletedProcess([], 0, output)
        with patch.object(jdk.subprocess, "run", return_value=result):
            with self.assertRaises(jdk.CachedJdkError):
                jdk.configure(self.env)

    def test_wrong_compiler_is_not_exported(self):
        outputs = [subprocess.CompletedProcess([], 0, self.properties().encode()),
                   subprocess.CompletedProcess([], 0, b"javac 21.0.1\n")]
        with patch.object(jdk.subprocess, "run", side_effect=outputs):
            with self.assertRaises(jdk.CachedJdkError):
                jdk.configure(self.env)
        self.assertEqual(self.environment_file.read_text(), "PRESERVED=yes\n")

    def test_nonzero_exit_and_oversized_output_fail_without_exports(self):
        for result in (subprocess.CompletedProcess([], 1, b"private diagnostic"),
                       subprocess.CompletedProcess([], 0, b"x" * 65_537)):
            with self.subTest(code=result.returncode), patch.object(jdk.subprocess, "run", return_value=result):
                with self.assertRaises(jdk.CachedJdkError):
                    jdk.configure(self.env)
            self.assertEqual(self.environment_file.read_text(), "PRESERVED=yes\n")

    def test_timeout_does_not_export_or_retry(self):
        timeout = subprocess.TimeoutExpired(["fixture"], 30)
        with patch.object(jdk.subprocess, "run", side_effect=timeout) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                jdk.configure(self.env)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(self.environment_file.read_text(), "PRESERVED=yes\n")

    def test_invalid_output_path_prevents_both_exports(self):
        env = dict(self.env, GITHUB_PATH="relative")
        with patch.object(jdk.subprocess, "run", side_effect=self.run_java):
            with self.assertRaises(jdk.CachedJdkError):
                jdk.configure(env)
        self.assertEqual(self.environment_file.read_text(), "PRESERVED=yes\n")


if __name__ == "__main__":
    unittest.main()
