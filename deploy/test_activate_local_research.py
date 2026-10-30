"""Public-only local model activation, resource gates and non-fabricated source provenance."""
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location("activate_local_research",Path(__file__).with_name("activate_local_research.py"))
subject=importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


def database():
    db=sqlite3.connect(":memory:")
    db.executescript("""CREATE TABLE osint_publications_v1(source_id,url,kind,primary_source,expires_at,object_sha,raw_sha,last_changed);
        CREATE TABLE osint_objects_v1(sha,title,body);
        CREATE TABLE osint_originals_v1(sha,media_type);""")
    return db


def insert(db, *, source="moex_reports",url="https://fs.moex.com/files/123",primary=1,expiry=2000,
           title="Synthetic test fixture only",body="Report line\nSecond full line",original=True,valid_hash=True):
    checksum=hashlib.sha256((title+"\0"+body).encode()).hexdigest() if valid_hash else "0"*64
    db.execute("INSERT INTO osint_objects_v1 VALUES(?,?,?)",(checksum,title,body))
    db.execute("INSERT INTO osint_publications_v1 VALUES(?,?,?,?,?,?,?,?)",(source,url,"report",primary,expiry,checksum,"pdf-hash",1000))
    if original:
        db.execute("INSERT INTO osint_originals_v1 VALUES('pdf-hash','application/pdf')")


class DocumentTests(unittest.TestCase):
    def test_only_public_tables_are_needed_and_body_is_exact(self):
        with closing(database()) as db:
            insert(db)
            result=subject.public_document(db,1000)
        self.assertEqual(result["body"],"Report line\nSecond full line")
        self.assertEqual(set(result),{"title","body","original_object_sha256","source_id"})

    def test_missing_original_expired_untrusted_or_changed_documents_are_rejected(self):
        changes=[{"original":False},{"expiry":999},{"primary":0},{"source":"unknown"},
            {"url":"http://fs.moex.com/files/123"},{"url":"https://example.invalid/report.pdf"},
            {"url":"https://password@fs.moex.com/files/123"},{"valid_hash":False},{"title":""}]
        for change in changes:
            with self.subTest(change=change),closing(database()) as db:
                insert(db,**change)
                with self.assertRaisesRegex(RuntimeError,"public_report_unavailable"):
                    subject.public_document(db,1000)

    def test_bounded_text_never_cuts_a_source_line(self):
        body="first complete line\n"+"x"*119990+"\nlast line"
        with closing(database()) as db:
            insert(db,body=body)
            result=subject.public_document(db,1000)
        self.assertEqual(result["body"],"first complete line")


class ActivationTests(unittest.TestCase):
    def test_failed_real_probe_disables_worker_and_removes_only_new_unit(self):
        for existed in (False,True):
            with self.subTest(existed=existed),tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                unit=root/"worker.service"
                database_path=root/"database.db"
                with closing(sqlite3.connect(database_path)) as db:
                    db.execute("CREATE TABLE placeholder(value)")
                if existed:
                    unit.write_bytes(b"staged-unit")
                def read(path,*_args):
                    if path.name=="preparation-receipt.json":
                        return json.dumps({"status":"prepared","source_commit":subject.SOURCE,"model_sha256":subject.MODEL_SHA}).encode()
                    return b"staged-unit"
                def command(args,**_kwargs):
                    if args[0]=="/usr/sbin/runuser":
                        raise RuntimeError("probe_failed")
                    return b""
                document={"title":"Public fixture","body":"Line"}
                with patch.object(subject,"UNIT",unit),patch.object(subject,"DATABASE",database_path),\
                    patch.object(subject,"SOCKET",SimpleNamespace(is_socket=lambda:True)),\
                    patch.object(subject,"FILES",{"deploy/analyst-local-research.service":hashlib.sha256(b"staged-unit").hexdigest()}),\
                    patch.object(subject,"regular",side_effect=read),patch.object(subject,"ensure_account"),\
                    patch.object(subject,"health"),patch.object(subject,"public_document",return_value=document),\
                    patch.object(subject.os,"getuid",return_value=0),patch.object(subject.os,"sysconf",side_effect=[2*1024*1024,4096]),\
                    patch.object(subject.os,"cpu_count",return_value=4),patch.object(subject,"command",side_effect=command) as commands:
                    with self.assertRaisesRegex(RuntimeError,"probe_failed"):
                        subject.activate({"payload":{"source_commit":subject.SOURCE}})
                self.assertIn((["/usr/bin/systemctl","disable","--now",subject.SERVICE],),[call.args for call in commands.call_args_list])
                self.assertEqual(unit.exists(),existed)
                if existed:
                    self.assertEqual(unit.read_bytes(),b"staged-unit")

    def test_small_host_rejected_before_corpus_read_or_commands(self):
        for memory_pages,cpu in [(1024*1024,4),(2*1024*1024,2)]:
            with self.subTest(cpu=cpu),patch.object(subject.os,"getuid",return_value=0),\
                patch.object(subject.os,"sysconf",side_effect=[memory_pages,4096]),\
                patch.object(subject.os,"cpu_count",return_value=cpu),patch.object(subject,"regular") as read,\
                patch.object(subject,"command") as command:
                with self.assertRaisesRegex(RuntimeError,"activation_host_too_small"):
                    subject.activate({"payload":{"source_commit":subject.SOURCE}})
                read.assert_not_called()
                command.assert_not_called()

    def test_model_user_cannot_be_root_login_user_or_other_group(self):
        group=SimpleNamespace(gr_gid=100)
        good={"pw_uid":200,"pw_gid":100,"pw_dir":"/nonexistent","pw_shell":"/usr/sbin/nologin"}
        self.assertTrue(subject.account_valid(SimpleNamespace(**good),group))
        for change in [{"pw_uid":0},{"pw_gid":101},{"pw_dir":"/root"},{"pw_shell":"/bin/bash"}]:
            self.assertFalse(subject.account_valid(SimpleNamespace(**{**good,**change}),group))

    def test_probe_passes_only_public_text_to_unprivileged_client(self):
        document={"title":"Public fixture","body":"Line","source_id":"moex_reports","original_object_sha256":"0"*64,"token":"must-not-pass"}
        response={"status":"source_excerpt_selection","trade_permission":False,"model_sha256":subject.MODEL_SHA,
                  "source_sha256":hashlib.sha256(b"Public fixture\nLine").hexdigest(),"excerpt_count":0,"seconds":1}
        with patch.object(subject,"command",return_value=json.dumps(response).encode()) as command:
            self.assertEqual(subject.smoke(document),response)
        args=command.call_args.args[0]
        self.assertEqual(args[:4],["/usr/sbin/runuser","-u","analyst-ai","--"])
        self.assertEqual(json.loads(command.call_args.kwargs["data"]),{"title":"Public fixture","body":"Line"})

    def test_changed_model_source_or_permission_is_not_a_successful_probe(self):
        doc={"title":"Public fixture","body":"Line"}
        good={"status":"source_excerpt_selection","trade_permission":False,"model_sha256":subject.MODEL_SHA,
              "source_sha256":hashlib.sha256(b"Public fixture\nLine").hexdigest()}
        for change in [{"trade_permission":True},{"source_sha256":"wrong"},{"model_sha256":"wrong"},{"status":"unavailable"}]:
            with self.subTest(change=change),patch.object(subject,"command",return_value=json.dumps({**good,**change}).encode()):
                with self.assertRaisesRegex(RuntimeError,"local_inference_failed"):
                    subject.smoke(doc)


if __name__ == "__main__":
    unittest.main()
