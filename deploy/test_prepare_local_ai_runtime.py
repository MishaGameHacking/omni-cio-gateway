"""Owner WSL staging contract tests with synthetic bytes; no cloud calls."""
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("preparation", Path(__file__).with_name("prepare_local_ai_runtime.py"))
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


class Response(io.BytesIO):
    def geturl(self):
        return "https://huggingface.co/synthetic-fixture"


class PreparationTests(unittest.TestCase):
    def test_stage_accepts_only_exact_source_scope(self):
        with patch.object(subject.os, "getuid", return_value=0), patch.object(subject, "prerequisites") as install:
            for payload in ({}, {"source_commit": "wrong"}, {"source_commit": subject.SOURCE, "command": "untrusted"}):
                with self.assertRaisesRegex(ValueError, "preparation_scope_invalid"):
                    subject.run({"payload": payload})
            install.assert_not_called()

    def test_non_root_rejected_before_installation(self):
        with patch.object(subject.os, "getuid", return_value=1000), patch.object(subject, "prerequisites") as install:
            with self.assertRaisesRegex(ValueError, "preparation_scope_invalid"):
                subject.run({"payload": {"source_commit": subject.SOURCE}})
            install.assert_not_called()

    def test_commands_do_not_inherit_credentials_or_restart_services(self):
        runner = Mock(return_value=Mock(returncode=0, stdout=b"ok"))
        with patch.dict(os.environ, {"TIMEWEB_CLOUD_TOKEN": "SENTINEL", "OPENAI_API_KEY": "SENTINEL"}):
            subject.command(["/usr/bin/git", "--version"], run=runner)
        env = runner.call_args.kwargs["env"]
        self.assertNotIn("TIMEWEB_CLOUD_TOKEN", env)
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(env["NEEDRESTART_MODE"], "l")

    def test_command_failure_does_not_include_raw_output(self):
        runner = Mock(return_value=Mock(returncode=1, stdout=b"PRIVATE", stderr=b"PRIVATE"))
        with self.assertRaisesRegex(ValueError, "^preparation_command_failed$"):
            subject.command(["/usr/bin/git", "--version"], run=runner)

    def test_unsafe_symlink_and_group_write_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            real = root / "real"
            real.write_bytes(b"sample")
            link = root / "link"
            link.symlink_to(real)
            with self.assertRaises(ValueError):
                subject.regular(link, 100)
            real.chmod(0o666)
            with self.assertRaises(ValueError):
                subject.regular(real, 100)

    def test_hardlink_not_accepted_as_owned_staging_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / "file"
            file.write_bytes(b"sample")
            (file.parent / "link").hardlink_to(file)
            with self.assertRaises(ValueError):
                subject.regular(file, 100)

    def test_download_verifies_exact_bytes_and_hash(self):
        data = b"synthetic-test-model"
        with tempfile.TemporaryDirectory() as temporary, patch.object(subject, "LOCAL", Path(temporary)), \
                patch.object(subject, "MODEL_BYTES", len(data)), patch.object(subject, "MODEL_SHA", hashlib.sha256(data).hexdigest()):
            opened = Mock(return_value=Response(data))
            subject.download_model(opened)
            self.assertEqual((Path(temporary) / "model.litertlm").read_bytes(), data)
            self.assertFalse((Path(temporary) / "model.partial").exists())
            self.assertEqual(opened.call_args.args[0].get_header("Accept-encoding"), "identity")

    def test_wrong_hash_and_oversize_are_cleaned_without_publishing_model(self):
        for data in (b"bad", b"oversized"):
            with tempfile.TemporaryDirectory() as temporary, patch.object(subject, "LOCAL", Path(temporary)), \
                    patch.object(subject, "MODEL_BYTES", 3), patch.object(subject, "MODEL_SHA", "0" * 64):
                with self.assertRaises(ValueError):
                    subject.download_model(Mock(return_value=Response(data)))
                self.assertFalse((Path(temporary) / "model.litertlm").exists())
                self.assertFalse((Path(temporary) / "model.partial").exists())

    def test_existing_unverified_model_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(subject, "LOCAL", Path(temporary)):
            model = Path(temporary) / "model.litertlm"
            model.write_bytes(b"existing")
            opener = Mock()
            with self.assertRaises(ValueError):
                subject.download_model(opener)
            opener.assert_not_called()
            self.assertEqual(model.read_bytes(), b"existing")

    def test_plain_http_redirect_rejected(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(subject, "LOCAL", Path(temporary)):
            response = Response(b"synthetic")
            response.geturl = lambda: "http://example.invalid"
            with self.assertRaisesRegex(ValueError, "insecure_model_redirect"):
                subject.download_model(Mock(return_value=response))

    def test_stage_files_never_replace_different_existing_bytes(self):
        data = b"public test source"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, local = root / "source", root / "local"
            source.mkdir()
            local.mkdir()
            (source / "backend").mkdir()
            (local / "backend").mkdir()
            (source / "backend/file.py").write_bytes(data)
            (local / "backend/file.py").write_bytes(b"different")
            manifest = {"backend/file.py": hashlib.sha256(data).hexdigest()}
            with patch.object(subject, "LOCAL", local), patch.object(subject, "FILES", manifest):
                with self.assertRaisesRegex(ValueError, "stage_file_changed"):
                    subject.stage_files(source)

    def test_native_installation_is_limited_to_needed_packages(self):
        with patch.object(subject.ctypes.util, "find_library", side_effect=["found", "found", None, "found", "found", "found"]), \
                patch.object(subject.shutil, "which", return_value="/usr/bin/git"), patch.object(subject, "command") as command:
            self.assertEqual(subject.prerequisites(), ["libatomic1"])
        self.assertEqual(command.call_args_list[1].args[0],
                         ["/usr/bin/apt-get", "install", "--no-install-recommends", "-y", "libatomic1"])


if __name__ == "__main__":
    unittest.main()
