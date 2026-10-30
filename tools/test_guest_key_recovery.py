import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from recover_guest_research import API_SERVER, Resumption

CHECK = "test $(id -u) = 0"
PUBLIC = "ssh-ed25519 unit-test-placeholder"
GUEST = {"id":9417611, "project_id":2941515, "availability_zone":"ams-1",
         "status":"on", "is_qemu_agent":True, "cpu":4, "ram":8192, "boot_mode":"default"}


class Transient(Exception):
    pass


class Fixture:
    def __init__(self, *, login=False, before_health=True, after_health=True, server=None,
                 response=204, assignment=None, failure=b"Permission denied (publickey)."):
        self.server = server or dict(GUEST)
        self.calls = []
        self.seconds = 0
        self.key_binding = [9417611] if assignment is None else assignment
        def api(verb,path):
            self.calls.append((verb,path))
            if (verb,path)==("GET","/ssh-keys/1"):
                return 200,{"ssh_key":{"id":1,"body":PUBLIC,"used_by":self.key_binding}}
            if (verb,path)==("GET",API_SERVER):
                return 200,{"server":self.server}
            if (verb,path)==("POST",API_SERVER+"/reboot"):
                if isinstance(response,Exception):
                    raise response
                return response,{}
            raise AssertionError("unexpected endpoint")
        def delay(seconds):
            self.seconds += seconds
        self.normal=Mock(return_value=b"authenticated")
        self.command=Mock(return_value=subprocess.CompletedProcess([],0 if login else 255,b"ok",failure))
        self.operation=Resumption(Transient,{"id":1,"public":PUBLIC},api,probe=self.command,
            sleep=delay,clock=lambda:self.seconds,
            health=lambda:after_health if self.mutations else before_health,
            normal_factory=lambda *_:self.normal)

    @property
    def mutations(self):
        return [op for op in self.calls if op[0]!="GET"]

    def run(self):
        return self.operation(["ssh"],CHECK)


class Recovery(unittest.TestCase):
    def test_working_key_avoids_reboot(self):
        test=Fixture(login=True)
        self.assertEqual(test.run(),b"ok")
        self.assertEqual(test.mutations,[])
        test.normal.assert_not_called()

    def test_normal_reboot_once_then_defer_to_pinned_verified_ssh(self):
        test=Fixture()
        self.assertEqual(test.run(),b"authenticated")
        self.assertEqual(test.run(),b"authenticated")
        self.assertEqual(test.mutations,[("POST",API_SERVER+"/reboot")])
        self.assertGreaterEqual(test.seconds,48)
        self.assertEqual(test.command.call_count,1)
        self.assertEqual(test.normal.call_count,2)

    def test_unknown_or_recovery_boot_and_invalid_server_never_mutate(self):
        for change in ({"boot_mode":None},{"boot_mode":"recovery_disk"},{"status":"off"},
                       {"is_qemu_agent":False},{"id":1},{"ram":4096}):
            with self.subTest(change=change):
                test=Fixture(server={**GUEST,**change})
                with self.assertRaises(RuntimeError):test.run()
                self.assertEqual(test.mutations,[])

    def test_other_connection_failures_do_not_trigger_reboot(self):
        for failure in [b"Host key verification failed.",b"Connection timed out",b"Connection reset by peer"]:
            test=Fixture(failure=failure)
            with self.subTest(failure=failure),self.assertRaises(RuntimeError):test.run()
            self.assertEqual(test.mutations,[])

    def test_unassigned_key_and_unhealthy_service_never_mutate(self):
        for test,err in [(Fixture(assignment=[]),Transient),(Fixture(assignment=[42]),RuntimeError),
                         (Fixture(before_health=False),RuntimeError)]:
            with self.assertRaises(err):test.run()
            self.assertEqual(test.mutations,[])

    def test_ambiguous_receipt_not_repeated_and_no_remote_action(self):
        for response in (500,OSError()):
            test=Fixture(response=response)
            with self.assertRaises((OSError,RuntimeError)):test.run()
            with self.assertRaises(RuntimeError):test.run()
            self.assertEqual(test.mutations,[("POST",API_SERVER+"/reboot")])
            test.normal.assert_not_called()

    def test_no_handoff_if_service_does_not_recover(self):
        test=Fixture(after_health=False)
        with self.assertRaisesRegex(RuntimeError,"post_reboot_health_unconfirmed"):test.run()
        test.normal.assert_not_called()
        self.assertLessEqual(test.seconds,216)


if __name__=="__main__":
    unittest.main()
