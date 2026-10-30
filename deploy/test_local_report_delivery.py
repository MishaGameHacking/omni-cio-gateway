"""Exercise temporary authorization and the actual new-module rollback path without network access."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"deploy"),str(ROOT/"tools")]
import gpt6_protocol_release as core
import local_report_route_release as release
import prepare_local_report_release as package
import timeweb_registered_ssh as ssh


class ProbeError(Exception):
    pass


def key(used,identifier=4,body="ssh-ed25519 public-test-only"):
    return {"ssh_key":{"id":identifier,"body":body,"used_by":used}}


class KeyAssignmentTests(unittest.TestCase):
    def test_ids_and_documented_server_objects_are_scoped_to_one_host(self):
        public="ssh-ed25519 public-test-only comment"
        for used in [[ssh.SERVER],[{"id":ssh.SERVER}],[{"server_id":str(ssh.SERVER)}]]:
            self.assertTrue(ssh.assignment(key(used),4,public))
        self.assertFalse(ssh.assignment(key([]),4,public))
        for document in [key([ssh.SERVER,123]),key([True]),key([{}]),key(None),key([ssh.SERVER],identifier=6),key([ssh.SERVER],body="ssh-ed25519 changed")]:
            with self.subTest(used=document["ssh_key"]["used_by"]),self.assertRaises(RuntimeError):
                ssh.assignment(document,4,public)

    def test_registry_pending_does_not_attempt_ssh(self):
        read,run,pause=Mock(return_value=(200,key([]))),Mock(),Mock()
        f=ssh.verified_remote(ProbeError,{"id":4,"public":"ssh-ed25519 public-test-only"},read,run=run,pause=pause,clock=lambda:100)
        with self.assertRaisesRegex(ProbeError,"assignment_pending"),redirect_stdout(io.StringIO()):
            f(["ssh"],"test $(id -u) = 0")
        read.assert_called_once_with("GET","/ssh-keys/4")
        run.assert_not_called()
        pause.assert_called_once_with(20)

    def test_bound_key_waits_only_for_guest_and_keeps_same_strict_command(self):
        read=Mock(return_value=(200,key([ssh.SERVER])))
        run=Mock(side_effect=[subprocess.CompletedProcess([],255,b"",b"Permission denied PRIVATE-DETAIL"),
                              subprocess.CompletedProcess([],0,b"ok",b"")])
        pause=Mock(); output=io.StringIO()
        f=ssh.verified_remote(ProbeError,{"id":4,"public":"ssh-ed25519 public-test-only"},read,run=run,pause=pause,clock=lambda:100)
        command=["ssh","-o","StrictHostKeyChecking=yes","root@target"]
        with redirect_stdout(output):
            with self.assertRaises(ProbeError):
                f(command,"test $(id -u) = 0")
            self.assertEqual(f(command,"test $(id -u) = 0"),b"ok")
        self.assertEqual(run.call_args_list[0],run.call_args_list[1])
        self.assertIn("StrictHostKeyChecking=yes",run.call_args_list[0].args[0])
        self.assertNotIn("PRIVATE",output.getvalue())
        pause.assert_called_once_with(20)

    def test_host_identity_change_aborts_without_delay(self):
        pause=Mock()
        f=ssh.verified_remote(ProbeError,{"id":4,"public":"ssh-ed25519 public-test-only"},
            Mock(return_value=(200,key([ssh.SERVER]))),run=Mock(return_value=subprocess.CompletedProcess([],255,b"",b"Host key verification failed")),pause=pause)
        with self.assertRaisesRegex(RuntimeError,"host_identity_rejected"),redirect_stdout(io.StringIO()):
            f(["ssh"],"test $(id -u) = 0")
        pause.assert_not_called()

    def test_propagation_deadline_disallows_another_connection(self):
        read,run,pause=Mock(return_value=(200,key([]))),Mock(),Mock()
        current=[100]
        f=ssh.verified_remote(ProbeError,{"id":4,"public":"ssh-ed25519 public-test-only"},read,run=run,pause=pause,clock=lambda:current[0])
        with self.assertRaises(ProbeError),redirect_stdout(io.StringIO()):
            f(["ssh"],"test $(id -u) = 0")
        current[0]=401
        with self.assertRaisesRegex(RuntimeError,"propagation_deadline"):
            f(["ssh"],"test $(id -u) = 0")
        self.assertEqual(read.call_count,1)
        run.assert_not_called()


class ReleaseTests(unittest.TestCase):
    def test_enablement_scopes_one_feature_flag_and_rolls_back_on_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"owner.service.d"/"79-local-research.conf"
            reload=Mock()
            with self.assertRaisesRegex(RuntimeError,"failed_probe"):
                with release.route_control(path,reload):
                    self.assertEqual(path.read_bytes(),b"[Service]\nEnvironment=LOCAL_RESEARCH_ENABLED=true\n")
                    raise RuntimeError("failed_probe")
            self.assertFalse(path.exists())
            self.assertEqual(reload.call_count,2)
            with release.route_control(path,reload):
                pass
            self.assertEqual(path.read_bytes(),release.SETTING)
            with self.assertRaisesRegex(RuntimeError,"already_configured"),release.route_control(path,reload):
                self.fail("Existing operator setting must be preserved")
            self.assertEqual(path.read_bytes(),release.SETTING)

    def test_unit_symlink_cannot_overwrite_another_setting(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); target=root/"protected";target.write_text("preserve")
            parent=root/"real";parent.mkdir();link=root/"alias";link.symlink_to(parent)
            with self.assertRaisesRegex(RuntimeError,"unsafe_unit_directory"),release.route_control(link/"setting",Mock()):
                self.fail("Symlink must be rejected")
            self.assertEqual(target.read_text(),"preserve")

    def test_worker_evidence_is_for_exact_model_source_and_bounded_task(self):
        valid={"status":"local_worker_active","server_id":9417611,"source_commit":release.SOURCE,
            "model_sha256":release.MODEL_SHA,"model_network_allowed":False,"model_broker_credentials":False,
            "smoke":{"status":"source_excerpt_selection","trade_permission":False,"model_sha256":release.MODEL_SHA}}
        release.check_worker(valid)
        for change in [{"source_commit":"old"},{"model_broker_credentials":True},{"model_network_allowed":True},
                       {"smoke":{**valid["smoke"],"trade_permission":True}},{"smoke":{"status":"unavailable"}}]:
            with self.subTest(change=change),self.assertRaisesRegex(RuntimeError,"qualified_local_worker_required"):
                release.check_worker({**valid,**change})

    def test_existing_module_restored_and_new_module_removed_after_activation_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); saved=root/"old";saved.mkdir()
            (root/"app.py").write_bytes(b"template")
            (root/"osint_worker.py").write_bytes(b"original")
            files={"local_research.py":{"before":None,"content":"new"},
                   "osint_worker.py":{"before":core.digest(b"original"),"content":"changed"}}
            def fail():
                self.assertEqual((root/"local_research.py").read_bytes(),b"new")
                self.assertEqual((root/"osint_worker.py").read_bytes(),b"changed")
                raise RuntimeError("activation_failed")
            with self.assertRaisesRegex(RuntimeError,"activation_failed"):
                core.install(root,saved,files,fail)
            self.assertFalse((root/"local_research.py").exists())
            self.assertEqual((root/"osint_worker.py").read_bytes(),b"original")

    def test_transport_composes_pinned_core_without_running_legacy_command(self):
        raw=(ROOT/"deploy/gpt6_protocol_release.py").read_bytes()
        extension=(ROOT/"deploy/local_report_route_release.py").read_bytes()
        self.assertEqual(hashlib.sha256((ROOT/"tools/prepare_gpt6_protocol_transport.py").read_bytes()).hexdigest(),package.VALIDATOR_HASH)
        namespace={"__name__":"assembled_release_test"}
        with patch.dict(sys.modules):
            exec(compile(package.operation(raw,extension),"assembled-release","exec"),namespace)
        self.assertEqual(namespace["SOURCE"],release.SOURCE)
        self.assertEqual(namespace["MODULES"],{"local_research.py","osint_worker.py"})
        with self.assertRaisesRegex(RuntimeError,"rollback_core_changed"):
            package.operation(raw+b"\n",extension)


if __name__=="__main__":
    unittest.main()
