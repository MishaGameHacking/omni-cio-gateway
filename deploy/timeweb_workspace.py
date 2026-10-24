#!/usr/bin/env python3
"""Sequential checks/build/runtime gates on the permanent Timeweb server."""
from __future__ import annotations
import datetime,fcntl,hashlib,json,os,pathlib,re,shutil,subprocess,sys,traceback,urllib.request
ROOT=pathlib.Path("/srv/analyst-ai/workspace")
STATE=pathlib.Path("/var/lib/analyst-ai-build")
SDK=pathlib.Path("/opt/analyst-android-sdk")
PY=STATE/"venv/bin/python"
CERT="bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1"
HOST="https://analyst-ai-2941515.twc1.net"
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1048576),b""):h.update(b)
    return h.hexdigest()
def write(path,data):
    temp=path.with_suffix(".next");temp.write_text(json.dumps(data,indent=2)+"\n");temp.chmod(0o640);os.replace(temp,path)
def source_hash():
    names=subprocess.check_output(["git","ls-files","--cached","--others","--exclude-standard","-z"],cwd=ROOT).split(b"\0")
    h=hashlib.sha256()
    for name in sorted(set(names)-{b""}):
        relative=os.fsdecode(name)
        if relative in ("AGENTS.md","README.md") or relative.startswith("docs/"):
            continue  # Documentation is not an APK or backend build input.
        p=ROOT/relative
        if p.is_file():
            h.update(name+b"\0"+sha(p).encode()+b"\0")
    return h.hexdigest()
def memory_kib():
    return int(next(x.split()[1] for x in pathlib.Path("/proc/meminfo").read_text().splitlines() if x.startswith("MemTotal:")))
def require_capacity(command):
    minimum={"check":0,"build":3500*1024,"runtime":5500*1024}[command]
    free={"check":512*1024**2,"build":7*1024**3,"runtime":10*1024**3}[command]
    if memory_kib()<minimum:raise RuntimeError("insufficient_physical_memory_for_"+command)
    if shutil.disk_usage(ROOT).free<free:raise RuntimeError("insufficient_free_disk_for_"+command)
def previous(stage,digest):
    p=STATE/(stage+"-result.json")
    d=json.loads(p.read_text()) if p.exists() else {}
    if d.get("status")!="passed" or d.get("source_sha256")!=digest:raise RuntimeError(stage+"_must_pass_for_current_sources")
    return d
def main():
    command=sys.argv[1] if len(sys.argv)==2 else "status"
    if command=="status":
        print(json.dumps({"workspace":str(ROOT),"memory_kib":memory_kib(),"disk_free_bytes":shutil.disk_usage(ROOT).free,
           "results":{c:json.loads((STATE/(c+"-result.json")).read_text()) for c in ("check","build","runtime") if (STATE/(c+"-result.json")).exists()}},indent=2));return
    if command not in ("check","build","runtime"):raise RuntimeError("unknown_workspace_stage")
    STATE.mkdir(exist_ok=True)
    with (STATE/"workspace.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        report={"stage":command,"status":"running","started_at":stamp(),"steps":[]}
        result=STATE/(command+"-result.json")
        folder=STATE/"runs"/(datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+command)
        folder.mkdir(parents=True,exist_ok=False);report["log_directory"]=str(folder)
        env=dict(os.environ)
        env.update({"ANDROID_HOME":str(SDK),"ANDROID_SDK_ROOT":str(SDK),"GRADLE_USER_HOME":"/var/cache/analyst-ai/gradle","JAVA_HOME":"/usr/lib/jvm/java-17-openjdk-amd64",
            "TELEGRAM_CLIENT_ID":"123456","TELEGRAM_CLIENT_SECRET":"test-only","BACKEND_PUBLIC_URL":"https://example.invalid",
            "FERNET_KEY":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=","ANALYSIS_SCHEDULER_ENABLED":"false","AI_EXTERNAL_PROCESSING_APPROVED":"false",
            "DATABASE_PATH":str(folder/"tests.sqlite3"),"PYTHONUNBUFFERED":"1"})
        def run(label,args,timeout=1800):
            log=folder/(label+".log")
            with log.open("w") as stream:
                code=subprocess.run([str(a) for a in args],cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout).returncode
            report["steps"].append({"name":label,"exit_code":code,"log":str(log)});write(result,report)
            print("WORKSPACE_STEP="+json.dumps({"stage":command,"name":label,"exit_code":code}),flush=True)
            if code:raise RuntimeError(label+"_failed")
        try:
            require_capacity(command)
            report["source_sha256"]=source_hash();write(result,report)
            run("diff-check",["git","diff","--check"])
            if command=="check":
                run("dependencies",[PY,"-m","pip","check"])
                run("python-source-audit",[PY,".github/scripts/audit_python_sources.py"])
                run("workspace-guard-tests",[PY,"-m","unittest","discover","-s","deploy/tests","-p","test_timeweb_workspace.py","-v"])
                run("host-tests",[PY,"-m","unittest","discover","-s",".github/scripts/tests","-p","test_*.py","-v"])
                run("tools-tests",[PY,"-m","unittest","discover","-s","tools/tests","-p","test_*.py","-v"])
                tests=sorted(str(p.relative_to(ROOT)) for p in (ROOT/".github/scripts").glob("*.test.cjs"))
                if tests:run("node-tests",["node","--test",*tests])
                run("backend-tests",[PY,"-m","pytest","backend/tests","-q","--junitxml="+str(folder/"backend-tests.xml")])
            elif command=="build":
                previous("check",report["source_sha256"])
                assert sha(ROOT/"gradle/wrapper/gradle-wrapper.jar")=="238e777fcddd7e34f9708186085def2abd6e08e658505b38718d79d74c21abd5"
                cert=subprocess.check_output(["keytool","-exportcert","-alias","androiddebugkey","-keystore",str(STATE/".android/debug.keystore"),"-storepass","android"],stderr=subprocess.DEVNULL)
                assert hashlib.sha256(cert).hexdigest()==CERT,"signing_identity_changed"
                run("assets",[PY,"tools/prepare_spectrum_checkout.py"])
                extra=[]
                try:
                    with urllib.request.urlopen("https://repo.maven.apache.org/maven2/junit/junit/4.13.2/junit-4.13.2.pom",timeout=10) as response:assert b"<artifactId>junit</artifactId>" in response.read(100000)
                except Exception:
                    with urllib.request.urlopen("https://maven-central.storage-download.googleapis.com/maven2/junit/junit/4.13.2/junit-4.13.2.pom",timeout=15) as response:assert b"<artifactId>junit</artifactId>" in response.read(100000)
                    init=folder/"maven-mirror.init.gradle"
                    init.write_text("settingsEvaluated { s -> [s.pluginManagement.repositories,s.dependencyResolutionManagement.repositories].each { rs -> rs.each { r -> if (r instanceof org.gradle.api.artifacts.repositories.MavenArtifactRepository && r.url.host == 'repo.maven.apache.org') r.setUrl('https://maven-central.storage-download.googleapis.com/maven2/') } } }\n")
                    extra=["--init-script",str(init)]
                run("gradle",["./gradlew",":app:testDebugUnitTest",":app:lintDebug",":app:lintPreview",":app:assembleDebug",":app:assembleRelease",":app:assemblePreview",":ci-ui-driver:lintDebug",":ci-ui-driver:assembleDebug","--no-daemon","--no-parallel","--max-workers=1",*extra],7200)
                run("mesh-apk-check",[PY,"tools/generate_spectrum_meshes.py","--check","--check-apk"])
                out=ROOT/"app/build/outputs/apk/preview";apk=out/"app-preview.apk";bt=SDK/"build-tools/37.0.0"
                for name,args in [("signature.txt",[bt/"apksigner","verify","--verbose","--print-certs",apk]),("alignment.txt",[bt/"zipalign","-c","-P","16","-v","4",apk]),("badging.txt",[bt/"aapt","dump","badging",apk]),("manifest.txt",[bt/"aapt","dump","xmltree",apk,"AndroidManifest.xml"])]:
                    with (out/name).open("w") as stream:subprocess.run([str(a) for a in args],env=env,stdout=stream,stderr=subprocess.STDOUT,check=True)
                run("apk-verification",[PY,".github/scripts/verify_apk.py"])
                report["apk_sha256"]=sha(apk);report["apk"]=str(apk)
            else:
                build=previous("build",report["source_sha256"])
                apk=ROOT/"app/build/outputs/apk/preview/app-preview.apk"
                assert sha(apk)==build["apk_sha256"],"apk_changed_since_build"
                run("runtime-sdk",[PY,".github/scripts/prepare_android_sdk.py","--sdk",SDK,"--runtime"],1800)
                lavapipe=list(pathlib.Path("/usr/share/vulkan/icd.d").glob("lvp_icd*.json"))
                assert len(lavapipe)==1,"lavapipe_not_installed"
                env.update({"RUN_PROFILE_UI_TESTS":"1","VK_ICD_FILENAMES":str(lavapipe[0])})
                old=STATE/"previous-0.10.0.apk"
                assert sha(old)=="3a31c602ec885a0d8cac8d76f43369cfb6ed3bdaa928f1cd7429582b0d5a40a3"
                for page in (16384,4096):
                    run("runtime-"+str(page),["xvfb-run","-a",PY,".github/scripts/test_apk_installation.py","--sdk",SDK,"--apk",apk,"--previous",old,"--api","37","--page-bytes",str(page),"--work-dir",ROOT/("app/build/outputs/apk/preview/install-api37-"+str(page))],7200)
                run("distribution",[PY,".github/scripts/validate_distribution.py"])
                report["apk_sha256"]=sha(apk)
            assert source_hash()==report["source_sha256"],"sources_changed_during_checks"
            report["status"]="passed"
        except BaseException as error:
            report["status"]="blocked" if str(error).startswith("insufficient_") else "failed"
            report["error"]=str(error);report["error_type"]=type(error).__name__
            with (folder/"failure.log").open("w") as log:traceback.print_exc(file=log)
        finally:
            report["finished_at"]=stamp();write(result,report)
            print("WORKSPACE_RESULT="+json.dumps(report),flush=True)
        if report["status"]!="passed":raise SystemExit(1)
if __name__=="__main__":main()
