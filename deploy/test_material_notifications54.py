import importlib.util
import json
from pathlib import Path
import sqlite3
import unittest
spec=importlib.util.spec_from_file_location("material54",Path(__file__).with_name("material_notifications54.py"))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class PreferencesTests(unittest.TestCase):
    def fixture(self):
        db=sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.executescript("""
        CREATE TABLE installation_owner(telegram_sub TEXT);
        CREATE TABLE users(id INTEGER,telegram_sub TEXT);
        CREATE TABLE workspace_notification_preferences(user_id INTEGER,version INTEGER,payload_json TEXT,applied_at INTEGER);
        CREATE TABLE analysis_profiles(user_id INTEGER,notify_briefs INTEGER,notify_critical INTEGER,updated_at INTEGER);
        CREATE TABLE workspace_notification_outbox(user_id INTEGER,kind TEXT,state TEXT,eligible_at INTEGER,claim_id TEXT,claim_expires_at INTEGER);
        INSERT INTO installation_owner VALUES ('fixture-owner');
        INSERT INTO users VALUES (1,'fixture-owner');
        INSERT INTO analysis_profiles VALUES (1,1,1,5);
        INSERT INTO workspace_notification_outbox VALUES (1,'brief','claimed',5,'fixture-claim',10),(1,'risk','pending',5,NULL,NULL),(1,'portfolio','pending',5,NULL,NULL);
        """)
        prefs=dict(timezone="Europe/Moscow",morning="09:00",evening="19:00",quiet_start="22:00",quiet_end="08:00",briefs_enabled=True,critical_enabled=True,enabled=True)
        db.execute("INSERT INTO workspace_notification_preferences VALUES(1,3,?,5)",(json.dumps(prefs),));db.commit()
        return db,prefs
    def test_changes_only_scheduled_briefs(self):
        db,before=self.fixture()
        result=m.apply_material_only(db,"fixture-owner",100)
        version,raw=db.execute("SELECT version,payload_json FROM workspace_notification_preferences").fetchone()
        self.assertEqual(version,4)
        self.assertEqual(json.loads(raw),before|{"briefs_enabled":False})
        self.assertEqual(dict(db.execute("SELECT kind,state FROM workspace_notification_outbox")),{"brief":"suppressed","risk":"pending","portfolio":"pending"})
        self.assertEqual(result["pending_briefs_suppressed"],1)
    def test_owner_mismatch_rolls_back(self):
        db,before=self.fixture()
        with self.assertRaisesRegex(RuntimeError,"owner_identity"):m.apply_material_only(db,"another-owner",100)
        self.assertEqual(json.loads(db.execute("SELECT payload_json FROM workspace_notification_preferences").fetchone()[0]),before)
    def test_repetition_is_idempotent(self):
        db,_=self.fixture();m.apply_material_only(db,"fixture-owner",100)
        self.assertFalse(m.apply_material_only(db,"fixture-owner",101)["changed"])
        self.assertEqual(db.execute("SELECT version FROM workspace_notification_preferences").fetchone()[0],4)
    def test_disabled_notifications_stay_disabled(self):
        db,before=self.fixture();before["enabled"]=False
        db.execute("UPDATE workspace_notification_preferences SET payload_json=?",(json.dumps(before),));db.commit()
        m.apply_material_only(db,"fixture-owner",100)
        self.assertFalse(json.loads(db.execute("SELECT payload_json FROM workspace_notification_preferences").fetchone()[0])["enabled"])
    def test_missing_profile_aborts_before_write(self):
        db,before=self.fixture();db.execute("DELETE FROM analysis_profiles");db.commit()
        with self.assertRaisesRegex(RuntimeError,"existing_analysis_profile"):m.apply_material_only(db,"fixture-owner",100)
        self.assertEqual(json.loads(db.execute("SELECT payload_json FROM workspace_notification_preferences").fetchone()[0]),before)
if __name__=="__main__":unittest.main()
