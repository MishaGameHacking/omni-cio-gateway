"""Apply the owner's material-events preference without changing other settings."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3
import time

FIELDS={"timezone","morning","evening","quiet_start","quiet_end","briefs_enabled","critical_enabled","enabled"}

def require(value, code):
    if not value:
        raise RuntimeError(code)

def apply_material_only(db, subject, at):
    try:
        db.execute("BEGIN IMMEDIATE")
        owners=db.execute("SELECT telegram_sub FROM installation_owner").fetchall()
        users=db.execute("SELECT id,telegram_sub FROM users").fetchall()
        require(len(owners)==len(users)==1 and owners[0][0]==users[0][1]==subject,"owner_identity_mismatch")
        user_id=users[0][0]
        row=db.execute("SELECT version,payload_json FROM workspace_notification_preferences WHERE user_id=?",(user_id,)).fetchone()
        require(row is not None,"existing_notification_preferences_required")
        value=json.loads(row[1])
        require(set(value)==FIELDS and all(type(value[k]) is bool for k in ("briefs_enabled","critical_enabled","enabled")),"notification_preferences_invalid")
        profile=db.execute("SELECT notify_briefs FROM analysis_profiles WHERE user_id=?",(user_id,)).fetchone()
        require(profile is not None,"existing_analysis_profile_required")
        if value["briefs_enabled"] is False and profile[0]==0:
            db.rollback()
            return {"changed":False,"briefs_enabled":False,"other_preferences_preserved":True}
        value["briefs_enabled"]=False
        cursor=db.execute("UPDATE workspace_notification_preferences SET version=version+1,payload_json=?,applied_at=? WHERE user_id=? AND version=?",
                          (json.dumps(value,ensure_ascii=False,separators=(",",":")),at,user_id,row[0]))
        require(cursor.rowcount==1,"notification_preferences_changed")
        db.execute("UPDATE analysis_profiles SET notify_briefs=0,updated_at=? WHERE user_id=?",(at,user_id))
        suppressed=db.execute("UPDATE workspace_notification_outbox SET state='suppressed',eligible_at=?,claim_id=NULL,claim_expires_at=NULL WHERE user_id=? AND kind='brief' AND state IN ('pending','claimed')",(at,user_id)).rowcount
        db.commit()
        return {"changed":True,"briefs_enabled":False,"other_preferences_preserved":True,"pending_briefs_suppressed":suppressed}
    except BaseException:
        db.rollback()
        raise

def main(envelope):
    require(os.getuid()==0,"runtime_admin_identity_required")
    payload=envelope["payload"]
    require(re.fullmatch(r"[0-9]{8,20}",str(payload["deployment_run"])) is not None,"invalid_deployment_run")
    receipt_path=Path("/var/lib/analyst-ai-build/development")/("server-runtime-"+str(payload["deployment_run"]))/"deployment.json"
    receipt=json.loads(receipt_path.read_text())
    require(receipt["status"]=="deployed" and receipt["source_commit"]==payload["source_commit"],"deployed_source_mismatch")
    for name,expected in receipt["installed_sha256"].items():
        require(re.fullmatch(r"[a-z_]+\.py",name) is not None,"invalid_runtime_module")
        require(hashlib.sha256((Path("/opt/analyst-ai/backend")/name).read_bytes()).hexdigest()==expected,"runtime_files_changed")
    env={}
    for line in Path("/etc/analyst-ai/backend.env").read_text().splitlines():
        key,sep,value=line.partition("=")
        if sep and not key.startswith("#"):
            parts=shlex.split(value)
            if len(parts)==1:env[key]=parts[0]
    subject=env.get("ANALYST_OWNER_TELEGRAM_SUB","")
    require(bool(subject),"owner_identity_missing")
    database=Path(env.get("DATABASE_PATH","/var/lib/analyst-ai/backend.db"))
    require(database.is_file() and not database.is_symlink() and database.resolve()==database and database.is_relative_to("/var/lib/analyst-ai"),"database_path_invalid")
    require(re.fullmatch(r"[0-9]{8,20}",str(envelope["run_id"])) is not None,"invalid_run")
    archive=Path("/var/lib/analyst-ai-build/development")/("material-notifications-"+str(envelope["run_id"]))
    archive.mkdir(mode=0o700)
    with closing(sqlite3.connect(database,timeout=15)) as db:
        with closing(sqlite3.connect(archive/"before.sqlite3")) as saved:db.backup(saved)
        (archive/"before.sqlite3").chmod(0o600)
        result=apply_material_only(db,subject,int(time.time()))
    report={**result,"status":"applied","server_id":9417611,"source_commit":payload["source_commit"],"at":datetime.now(timezone.utc).isoformat(),"product_tests_executed":False}
    (archive/"receipt.json").write_text(json.dumps(report),encoding="utf-8")
    print("MATERIAL_NOTIFICATIONS="+json.dumps(report),flush=True)

if __name__=="__main__":
    try:main(ENVELOPE)
    except Exception as error:
        code=str(error)
        if not re.fullmatch(r"[a-z_]{1,100}",code):code=type(error).__name__
        print(json.dumps({"status":"failed","code":code}),flush=True)
        raise
