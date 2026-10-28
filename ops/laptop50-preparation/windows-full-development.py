"""Reviewed operator bootstrap: real Windows source edits/checks/build, no runtime or publication."""
from __future__ import annotations
import argparse,base64,ctypes,datetime,hashlib,io,json,os,pathlib,re,shutil,stat,subprocess,sys,tarfile,tempfile,time,traceback,zipfile,zlib
from ctypes import wintypes

BASE_COMMIT = "5e35c9a7c7ee3aa402f264ce312f59c121617ddc"
BASE_SOURCE = "ccb895a11da33f75655b96b24e6355b599132ae41de213b743a4c9135a6759a7"
CERT = "bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1"
SDK = pathlib.Path(r"C:\actions-runner-2\_work\_tool\AndroidSdk\sdk")
CACHE = pathlib.Path(r"C:\actions-runner-2\_work\_tool")
JAVA = CACHE / "Java_Temurin-Hotspot_jdk/17.0.20-101/x64"
LEASE_BLOB = "c9626f3bf90b612a71b9bbf2954d0c134aa29b22"
MAX_ARCHIVE = 512*1024**2
MAX_WORK_SECONDS = 10800

def need(value, message):
    if not value: raise RuntimeError(message)

def stamp(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(data): return hashlib.sha256(data).hexdigest()
def git_blob(data): return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024**2),b""): h.update(block)
    return h.hexdigest()
def save(path, value):
    temporary=path.with_name(path.name+".next")
    temporary.write_text(json.dumps(value,ensure_ascii=True,indent=2)+"\n",encoding="utf-8",newline="\n")
    os.replace(temporary,path)
def checked(path, directory=False):
    info=path.lstat()
    need(not stat.S_ISLNK(info.st_mode) and not getattr(info,"st_file_attributes",0)&0x400,"linked_or_reparse_path")
    need((stat.S_ISDIR if directory else stat.S_ISREG)(info.st_mode),"unexpected_path_type")
    if not directory: need(info.st_nlink==1,"hardlinked_file")
    need(path.resolve(strict=True)==path,"noncanonical_path")
    return info

def paths():
    need(__debug__ and sys.platform=="win32" and os.environ.get("COMPUTERNAME")=="LAPTOP-NPSGA016","wrong_execution_host")
    need(os.environ.get("RUNNER_OS")=="Windows" and os.environ.get("RUNNER_ARCH")=="X64","wrong_runner_platform")
    need(sys.version_info[:3]==(3,14,6) and sys.maxsize>2**32,"unexpected_python_runtime")
    run,attempt=os.environ["GITHUB_RUN_ID"],os.environ["GITHUB_RUN_ATTEMPT"]
    need(re.fullmatch(r"[1-9]\d{0,19}",run) and re.fullmatch(r"[1-9]\d{0,4}",attempt),"invalid_run_identity")
    need(os.environ.get("GITHUB_REPOSITORY")=="MishaGameHacking/omni-cio-gateway","wrong_repository")
    workspace=pathlib.Path(os.environ["GITHUB_WORKSPACE"]).resolve(strict=True)
    permitted=[pathlib.Path(r"C:\actions-runner"+suffix)/"_work/omni-cio-gateway/omni-cio-gateway" for suffix in ("","-2","-3","-4")]
    need(workspace in permitted,"unexpected_runner_workspace")
    root=workspace/("windows-development-"+run+"-"+attempt)
    need(pathlib.Path(os.environ["SOURCE_ROOT"]).resolve(strict=True)==root,"wrong_owned_checkout")
    for p in (workspace,root): checked(p,True)
    state=pathlib.Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)/("analyst-development-"+run+"-"+attempt)
    return root,state,run,attempt

def git(root,state,*args):
    output=state/"git-read.bin"; errors=state/"git-read.stderr.log"
    with output.open("wb") as out, errors.open("wb") as err:
        subprocess.run(["git",*args],cwd=root,stdin=subprocess.DEVNULL,stdout=out,stderr=err,check=True,timeout=45)
    need(output.stat().st_size<=4*1024**2,"oversized_git_result")
    return output.read_bytes()

def inventory(root,state):
    names=sorted(set(git(root,state,"ls-files","--cached","--others","--exclude-standard","-z").split(b"\0"))-{b""})
    result={}; h=hashlib.sha256(); complete=hashlib.sha256()
    for name in names:
        rel=name.decode("utf-8"); path=root/rel
        need("\\" not in rel and not pathlib.PurePosixPath(rel).is_absolute() and ".." not in pathlib.PurePosixPath(rel).parts,"unsafe_source_path")
        if not path.is_file(): continue
        checked(path)
        value={"bytes":path.stat().st_size,"sha256":sha(path)}; result[rel]=value
        complete.update(name+b"\0"+value["sha256"].encode()+b"\0")
        if rel not in ("AGENTS.md","README.md") and not rel.startswith("docs/"):
            h.update(name+b"\0"+value["sha256"].encode()+b"\0")
    need(result,"empty_source_inventory")
    return h.hexdigest(),result,complete.hexdigest()

def apply_bundles(root,state,manifest):
    checked(manifest); specification=json.loads(manifest.read_text(encoding="utf-8"))
    need(specification.get("schema")==1 and specification.get("base_commit")==BASE_COMMIT,"invalid_patch_manifest")
    bundles=specification.get("bundles")
    need(isinstance(bundles,list) and 1<=len(bundles)<=8,"invalid_bundle_count")
    planned=[]; seen=set(); receipts=[]
    for item in bundles:
        need(isinstance(item,dict) and re.fullmatch(r"[a-z0-9_-]{1,64}",item.get("name","")),"invalid_bundle_name")
        path=manifest.parent/(item["name"]+".b64"); checked(path)
        encoded=path.read_bytes(); need(len(encoded)<=4*1024**2 and digest(encoded)==item["transport_sha256"],"patch_transport_changed")
        compressed=base64.b64decode(encoded,validate=True); decoder=zlib.decompressobj()
        raw=decoder.decompress(compressed,16*1024**2+1)
        need(len(raw)<=16*1024**2 and decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data,"invalid_patch_compression")
        need(digest(raw)==item["decoded_sha256"],"patch_payload_changed")
        bundle=json.loads(raw)
        need(bundle.get("reference_commit")==BASE_COMMIT,"wrong_patch_base")
        files=bundle.get("files"); need(isinstance(files,list) and 1<=len(files)<=100,"invalid_patch_files")
        for entry in files:
            rel=entry.get("path"); need(isinstance(rel,str) and rel.casefold() not in seen,"duplicate_patch_path")
            parts=pathlib.PurePosixPath(rel).parts
            need(parts and not pathlib.PurePosixPath(rel).is_absolute() and all(p not in (".","..") and re.fullmatch(r"[A-Za-z0-9_.-]+",p) and not p.endswith(".") for p in parts),"unsafe_patch_path")
            need(parts[0] in {"app","backend","deploy","tools","ci-ui-driver","gradle",".github","AGENTS.md","README.md","docs","gradle.properties","build.gradle.kts","settings.gradle.kts"},"patch_scope_not_reviewed")
            need(parts[0]!=".github" or len(parts)>2 and parts[1]=="scripts","workflow_mutation_not_allowed")
            need(rel not in (".github/scripts/emulator_lease.py",".github/scripts/ci_private_transfer.cjs"),"operator_boundary_patch_not_allowed")
            need(not any(p.lower() in {".git",".env","local.properties"} or p.lower().endswith((".jks",".keystore",".pem",".key")) for p in parts),"private_file_patch_forbidden")
            path=root.joinpath(*parts)
            for parent in reversed(path.parents):
                if parent==root or root in parent.parents:
                    if parent.exists(): checked(parent,True)
            content=entry.get("content"); need(isinstance(content,str) and "\0" not in content,"invalid_patch_content")
            new=content.encode("utf-8"); need(len(new)<=2*1024**2 and digest(new)==entry["new_sha256"],"patch_new_hash_mismatch")
            if entry.get("new_bytes") is not None: need(len(new)==entry["new_bytes"],"patch_new_size_mismatch")
            if entry.get("old_git_blob") is None:
                need(entry.get("old_sha256") is None and not path.exists() and not path.is_symlink(),"new_patch_file_exists")
                old=None
            else:
                checked(path); old=path.read_bytes()
                need(digest(old)==entry["old_sha256"] and git_blob(old)==entry["old_git_blob"],"patch_original_changed")
                need(git(root,state,"rev-parse","HEAD:"+rel).decode().strip()==entry["old_git_blob"],"patch_wrong_committed_blob")
                if entry.get("old_bytes") is not None: need(len(old)==entry["old_bytes"],"patch_old_size_mismatch")
            seen.add(rel.casefold()); planned.append((path,new,old))
            receipts.append({"bundle":item["name"],"path":rel,"old_sha256":entry.get("old_sha256"),"new_sha256":digest(new)})
    for path,new,old in planned:
        if old is not None: need(path.read_bytes()==old,"patch_input_changed_during_review")
        else: need(not path.exists(),"new_patch_file_appeared")
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_name(path.name+".reviewed-next")
        with temporary.open("xb") as out: out.write(new); out.flush(); os.fsync(out.fileno())
        os.replace(temporary,path); need(sha(path)==digest(new),"applied_patch_hash_mismatch")
    save(state/"applied-patches.json",{"manifest_sha256":sha(manifest),"bundles":bundles,"files":receipts})
    return receipts

def test_environment(state):
    env=dict(os.environ)
    for key in list(env):
        if key.startswith(("AI_","ANALYSIS_","TINVEST_","TELEGRAM_","FERNET_","OWNER_","OPENAI_","ANTHROPIC_","TIMEWEB_")) or key in {"GITHUB_TOKEN","GH_TOKEN","ACTIONS_RUNTIME_TOKEN","DATABASE_PATH","PYTHONPATH","PYTHONHOME","PYTHONOPTIMIZE"}:
            env.pop(key,None)
    home=pathlib.Path(os.environ["USERPROFILE"]).resolve(strict=True)
    need(home.name.lower()=="networkservice","unexpected_signing_service_profile")
    for p in (home/".gradle",home/".android"): checked(p,True)
    for name,expected in (("GRADLE_USER_HOME",home/".gradle"),("ANDROID_USER_HOME",home/".android"),("ANDROID_SDK_HOME",home)):
        if os.environ.get(name): need(pathlib.Path(os.environ[name]).resolve(strict=True)==expected,"existing_profile_override_mismatch:"+name)
    env.update({"JAVA_HOME":str(JAVA),"JAVA_HOME_17_X64":str(JAVA),"ANDROID_SDK_ROOT":str(SDK),"ANDROID_HOME":str(SDK),
        "ANDROID_USER_HOME":str(home/".android"),"GRADLE_USER_HOME":str(home/".gradle"),
        "PATH":str(JAVA/"bin")+os.pathsep+env["PATH"],"TELEGRAM_CLIENT_ID":"123456","TELEGRAM_CLIENT_SECRET":"test-only",
        "BACKEND_PUBLIC_URL":"https://example.invalid","TELEGRAM_REDIRECT_URI":"https://example.invalid/auth/telegram/callback",
        "FERNET_KEY":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=","DATABASE_PATH":str(state/"tests.sqlite3"),
        "ANALYSIS_SCHEDULER_ENABLED":"false","AI_EXTERNAL_PROCESSING_APPROVED":"false",
        "PYTHONUNBUFFERED":"1","PYTHONIOENCODING":"utf-8",
        "PYTHONUTF8":"1","PIP_CONFIG_FILE":os.devnull,"PIP_DISABLE_PIP_VERSION_CHECK":"1"})
    return env,home/".android/debug.keystore"

def linux_backend(root,state,expected,files,run):
    claim=pathlib.Path('C:/actions-runner-2/_work/_tool/AnalystLinux/analyst-project-distribution.json')
    checked(claim)
    value=json.loads(claim.read_text(encoding='utf-8'))
    need(value['distribution']=='Ubuntu-24.04' and value['host']=='LAPTOP-NPSGA016' and value.get('completed_at'),'unverified_linux_distribution')
    archive=state/'linux-source.tar'
    rows=[{'path':name,**identity} for name,identity in files.items()]
    with tarfile.open(archive,'x') as tar:
        for row in rows:
            data=(root/row['path']).read_bytes()
            need(len(data)==row['bytes'] and sha(root/row['path'])==row['sha256'],'linux_source_changed')
            entry=tarfile.TarInfo(row['path']);entry.size=len(data);entry.mode=0o644
            tar.addfile(entry,io.BytesIO(data))
    manifest=state/'linux-source-manifest.json'
    save(manifest,{'source_sha256':expected,'files':rows})
    def guest_path(path):
        p=path.resolve(strict=True)
        need(p.drive.upper()=='C:','unsupported_linux_transport_drive')
        return '/mnt/c/'+'/'.join(p.parts[1:])
    guest=pathlib.Path(os.environ['PATCH_DIR'])/'n00-linux-guest.py'
    checked(guest)
    destination=state/'linux-evidence.zip'
    linux_root='/opt/analyst-ci/runs/'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT']
    export='/mnt/c/'+'/'.join(destination.parts[1:])
    args=['wsl.exe','--distribution','Ubuntu-24.04','--user','analyst-ci','--exec','/usr/bin/timeout','--kill-after=15s','1800s',
          '/usr/bin/python3',guest_path(guest),guest_path(archive),sha(archive),guest_path(manifest),sha(manifest),linux_root,export]
    try:
        run('backend-tests',args,1850)
    finally:
        if destination.is_file():
            with zipfile.ZipFile(destination) as z:
                for name in z.namelist():
                    need(pathlib.PurePosixPath(name).name==name and name.endswith(('.json','.log','.xml')),'invalid_linux_evidence_entry')
                    need(z.getinfo(name).file_size<64*1024**2,'oversized_linux_evidence')
                    target=state/('linux-'+name)
                    with target.open('xb') as out:out.write(z.read(name))
        run('stop-owned-linux-distribution',['wsl.exe','--terminate','Ubuntu-24.04'],60)

def worker(root,state,manifest):
    report=json.loads((state/"windows-development.json").read_text(encoding="utf-8"))
    current="prepare"; serial=0
    def persist(): save(state/"windows-development.json",report)
    def run(label,args,timeout=1800,output=None,env=None):
        nonlocal serial
        serial+=1; target=output or state/(f"{serial:02d}-"+label+".log")
        target.parent.mkdir(parents=True,exist_ok=True)
        row={"label":label,"command":[str(x) for x in args],"started_at":stamp(),"timeout_seconds":timeout,"log":str(target),"exit_code":None}
        report["steps"].append(row); persist()
        print("WINDOWS_DEVELOPMENT_STEP="+json.dumps({"label":label,"status":"running"}),flush=True)
        start=time.monotonic()
        try:
            with target.open("xb") as out:
                child=subprocess.run([str(x) for x in args],cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,timeout=timeout)
            row["exit_code"]=child.returncode
            need(child.returncode==0,"step_failed:"+label)
        except BaseException as error:
            row["error_type"]=type(error).__name__; raise
        finally:
            row.update(finished_at=stamp(),duration_seconds=round(time.monotonic()-start,3))
            if target.exists(): row.update(log_bytes=target.stat().st_size,log_sha256=sha(target))
            persist(); print("WINDOWS_DEVELOPMENT_STEP="+json.dumps({"label":label,"exit_code":row["exit_code"],"duration_seconds":row["duration_seconds"]}),flush=True)
    try:
        need(git(root,state,"rev-parse","HEAD").decode().strip()==BASE_COMMIT,"wrong_source_head")
        before,files,complete_before=inventory(root,state); need(before==BASE_SOURCE,"base_source_bytes_changed")
        save(state/"source-before.json",{"source_sha256":before,"complete_source_sha256":complete_before,"files":files})
        report["patch_files"]=apply_bundles(root,state,manifest)
        expected,files,complete_expected=inventory(root,state); report["source_sha256"]=expected; report["complete_source_sha256"]=complete_expected
        need(all(row["path"] in files and files[row["path"]]["sha256"]==row["new_sha256"] for row in report["patch_files"]),"applied_patch_missing_from_source_inventory")
        save(state/"source-after-patches.json",{"source_sha256":expected,"complete_source_sha256":complete_expected,"files":files}); persist()
        env,key=test_environment(state); checked(key); report["signing_keystore_sha256_before"]=sha(key)
        sys.path[:0]=[str(root/".github/scripts"),str(root)]
        import verify_cached_jdk as jdk
        need(jdk.discover(str(CACHE))==JAVA,"unexpected_java_cache")
        report["java_runtime"]=jdk.verify(JAVA,env)
        properties=state/"java-default-profile.log"
        run("java-default-profile",[JAVA/"bin/java.exe","-XshowSettings:properties","-version"],30,output=properties,env=env)
        homes=re.findall(r"^\s*user\.home\s*=\s*(.+?)\s*$",properties.read_text(encoding="utf-8",errors="replace"),re.MULTILINE)
        need(len(homes)==1 and pathlib.Path(homes[0]).resolve(strict=True)==key.parent.parent,"java_service_home_changed")
        report["profile_locations"]={"java_user_home":str(key.parent.parent),"gradle_user_home":env["GRADLE_USER_HOME"],"android_user_home":env["ANDROID_USER_HOME"],"existing_debug_keystore":str(key),"profile_directory_created":False}
        import prepare_android_sdk as sdk
        from backend.android_runtime_contract import required_sdk_packages
        checked(SDK,True); report["sdk_packages"]={}
        for package in required_sdk_packages():
            sdk._verify_package(SDK,package)
            directory=SDK.joinpath(*package.split(";"))
            report["sdk_packages"][package]={name:sha(directory/name) for name in ("source.properties","package.xml") if (directory/name).is_file()}
        need(sha(root/"gradle/wrapper/gradle-wrapper.jar")=="238e777fcddd7e34f9708186085def2abd6e08e658505b38718d79d74c21abd5","gradle_wrapper_changed")
        certificate=state/"signing-certificate.der"
        with certificate.open("xb") as out,(state/"signing-keytool.stderr.log").open("xb") as err:
            subprocess.run([str(JAVA/"bin/keytool.exe"),"-exportcert","-alias","androiddebugkey","-keystore",str(key),"-storepass","android"],stdin=subprocess.DEVNULL,stdout=out,stderr=err,check=True,timeout=30,env=env)
        need(sha(certificate)==CERT,"signing_certificate_changed")
        report["certificate_sha256"]=CERT; persist()
        class Memory(ctypes.Structure):
            _fields_=[("Length",wintypes.DWORD),("Load",wintypes.DWORD)]+[(name,ctypes.c_ulonglong) for name in ("TotalPhys","AvailPhys","TotalPageFile","AvailPageFile","TotalVirtual","AvailVirtual","AvailExtendedVirtual")]
        memory=Memory(); memory.Length=ctypes.sizeof(memory)
        kernel=ctypes.WinDLL("kernel32",use_last_error=True); kernel.GlobalMemoryStatusEx.argtypes=[ctypes.POINTER(Memory)]; kernel.GlobalMemoryStatusEx.restype=wintypes.BOOL
        if not kernel.GlobalMemoryStatusEx(ctypes.byref(memory)): raise ctypes.WinError(ctypes.get_last_error())
        report["capacity"]={"physical_bytes":memory.TotalPhys,"available_bytes":memory.AvailPhys,"disk_free_bytes":shutil.disk_usage(root).free,"logical_cpus":os.cpu_count(),"observed_at":stamp()}
        need(memory.TotalPhys>=3500*1024**2,"insufficient_physical_memory_for_build")
        need(report["capacity"]["disk_free_bytes"]>=7*1024**3,"insufficient_free_disk_for_build"); persist()
        venv=state/"venv"; need(not venv.exists(),"venv_already_exists")
        run("venv",[sys.executable,"-m","venv",venv],300,env=env)
        py=venv/"Scripts/python.exe"; checked(py)
        run("install-test-requirements",[py,"-m","pip","--require-virtualenv","install","--no-input","--no-cache-dir","--index-url","https://pypi.org/simple","-r",root/"backend/requirements-dev.txt"],900,env=env)
        run("install-native-tls-requirements",[py,"-m","pip","--require-virtualenv","install","--no-input","--no-cache-dir","--index-url","https://pypi.org/simple","--require-hashes","--only-binary=:all:","-r",root/"tools/timeweb-actions-requirements.txt"],900,env=env)
        run("resolved-test-dependencies",[py,"-m","pip","freeze","--all"],60,env=env)
        current="check"; report["check"]={"status":"running","started_at":stamp()}; persist()
        checks=[("diff-check",["git","diff","--check"]),("dependencies",[py,"-m","pip","check"]),
            ("python-source-audit",[py,".github/scripts/audit_python_sources.py"]),
            ("workspace-guard-tests",[py,"-m","unittest","discover","-s","deploy/tests","-p","test_timeweb_workspace.py","-v"]),
            ("host-tests",[py,"-m","unittest","discover","-s",".github/scripts/tests","-p","test_*.py","-v"]),
            ("tools-tests",[py,"-m","unittest","discover","-s","tools/tests","-p","test_*.py","-v"])]
        for label,args in checks: run(label,args,env=env)
        nodes=sorted(str(p.relative_to(root)) for p in (root/".github/scripts").glob("*.test.cjs")); need(nodes,"node_test_files_missing")
        run("node-tests",["node","--test",*nodes],env=env)
        backend_check_failed = False
        try:
            linux_backend(root,state,expected,files,run)
        except RuntimeError as failure:
            if str(failure) != "step_failed:backend-tests":
                raise
            backend_check_failed = True
            report["backend_check_failure"] = "step_failed:backend-tests"
            # Preserve the failed gate while allowing independent APK build evidence.
            # The complete POSIX suite runs in the laptop-owned WSL distribution.
            persist()
        after=inventory(root,state); need(after[0]==expected and after[2]==complete_expected,"sources_changed_during_checks")
        report["check"].update(status="failed" if backend_check_failed else "passed",finished_at=stamp(),source_sha256=expected); persist()
        current="build"; report["build"]={"status":"running","started_at":stamp()}; persist()
        run("assets",[py,"tools/prepare_spectrum_checkout.py"],120,env=env)
        run("native-alignment-tests",[py,"tools/test_native_alignment.py"],180,env=env)
        run("mesh-tests",[py,"tools/test_spectrum_meshes.py"],180,env=env)
        tasks=[":app:testDebugUnitTest",":app:lintDebug",":app:lintPreview",":app:assembleDebug",":app:assembleRelease",":app:assemblePreview",":ci-ui-driver:lintDebug",":ci-ui-driver:assembleDebug"]
        run("gradle",[os.environ["COMSPEC"],"/d","/c",str(root/"gradlew.bat"),*tasks,"--no-daemon","--parallel","--max-workers=2","--stacktrace"],7200,env=env)
        run("mesh-apk-check",[py,"tools/generate_spectrum_meshes.py","--check","--check-apk"],180,env=env)
        out=root/"app/build/outputs/apk/preview"; apk=out/"app-preview.apk"; bt=SDK/"build-tools/37.0.0"
        static=[("signature.txt",[JAVA/"bin/java.exe","-jar",bt/"lib/apksigner.jar","verify","--verbose","--print-certs",apk]),
            ("alignment.txt",[bt/"zipalign.exe","-c","-P","16","-v","4",apk]),
            ("badging.txt",[bt/"aapt.exe","dump","badging",apk]),("manifest.txt",[bt/"aapt.exe","dump","xmltree",apk,"AndroidManifest.xml"])]
        for name,args in static: run("apk-"+name,args,90,output=out/name,env=env)
        run("apk-verification",[py,".github/scripts/verify_apk.py"],120,env=env)
        report["apks"]={}
        for relative in ("app/build/outputs/apk/debug/app-debug.apk","app/build/outputs/apk/preview/app-preview.apk","app/build/outputs/apk/release/app-release-unsigned.apk","ci-ui-driver/build/outputs/apk/debug/ci-ui-driver-debug.apk"):
            path=root/relative; checked(path); report["apks"][relative]={"bytes":path.stat().st_size,"sha256":sha(path)}
        after=inventory(root,state); need(after[0]==expected and after[2]==complete_expected,"sources_changed_during_build")
        need(sha(key)==report["signing_keystore_sha256_before"],"signing_keystore_changed")
        report["build"].update(status="passed",finished_at=stamp(),source_sha256=expected,apk_sha256=sha(apk)); report["status"]="failed_checks_build_passed" if backend_check_failed else "passed_check_and_build_only"
    except BaseException as error:
        report["status"]="failed"; report["failed_stage"]=current; report["error_type"]=type(error).__name__; report["error"]=str(error)[:500]
        if current in ("check","build") and report.get(current,{}).get("status")=="running": report[current].update(status="failed",finished_at=stamp())
        with (state/"failure.log").open("w",encoding="utf-8") as out: traceback.print_exc(file=out)
        raise
    finally:
        report["finished_at"]=stamp()
        try:
            final,files,complete_final=inventory(root,state); report["source_sha256_after"]=final; report["complete_source_sha256_after"]=complete_final
            save(state/"source-final.json",{"source_sha256":final,"complete_source_sha256":complete_final,"files":files})
            if report.get("source_sha256") is not None and (final!=report["source_sha256"] or complete_final!=report["complete_source_sha256"]): report["status"]="failed_integrity"
        except BaseException as error: report["status"]="failed_integrity"; report["final_inventory_error"]=type(error).__name__
        persist()
    need(report["status"]=="passed_check_and_build_only","final_integrity_failure")

class OwnedJob:
    """Only the handshake-blocked worker and its descendants enter this OS job."""
    def __init__(self):
        class Limits(ctypes.Structure):
            _fields_=[("ProcessTime",ctypes.c_longlong),("JobTime",ctypes.c_longlong),("Flags",wintypes.DWORD),("MinWorking",ctypes.c_size_t),("MaxWorking",ctypes.c_size_t),("ActiveLimit",wintypes.DWORD),("Affinity",ctypes.c_size_t),("Priority",wintypes.DWORD),("Scheduling",wintypes.DWORD)]
        class IO(ctypes.Structure): _fields_=[(name,ctypes.c_ulonglong) for name in ("ReadOps","WriteOps","OtherOps","ReadBytes","WriteBytes","OtherBytes")]
        class Extended(ctypes.Structure): _fields_=[("Basic",Limits),("IO",IO),("ProcessMemory",ctypes.c_size_t),("JobMemory",ctypes.c_size_t),("PeakProcess",ctypes.c_size_t),("PeakJob",ctypes.c_size_t)]
        self.api=ctypes.WinDLL("kernel32",use_last_error=True)
        signatures={"CreateJobObjectW":([ctypes.c_void_p,wintypes.LPCWSTR],wintypes.HANDLE),"SetInformationJobObject":([wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD],wintypes.BOOL),"AssignProcessToJobObject":([wintypes.HANDLE,wintypes.HANDLE],wintypes.BOOL),"OpenProcess":([wintypes.DWORD,wintypes.BOOL,wintypes.DWORD],wintypes.HANDLE),"QueryInformationJobObject":([wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p],wintypes.BOOL),"TerminateJobObject":([wintypes.HANDLE,wintypes.UINT],wintypes.BOOL),"CloseHandle":([wintypes.HANDLE],wintypes.BOOL)}
        for name,(args,result) in signatures.items(): function=getattr(self.api,name); function.argtypes=args; function.restype=result
        self.handle=self.api.CreateJobObjectW(None,None)
        if not self.handle: raise ctypes.WinError(ctypes.get_last_error())
        info=Extended(); info.Basic.Flags=0x2000
        if not self.api.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)):
            error=ctypes.WinError(ctypes.get_last_error()); self.close(); raise error
    def attach(self,process):
        need(process.poll() is None,"worker_exited_before_job_assignment")
        handle=self.api.OpenProcess(0x0100|0x0001,False,process.pid)
        if not handle: raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.api.AssignProcessToJobObject(self.handle,handle): raise ctypes.WinError(ctypes.get_last_error())
        finally: self.api.CloseHandle(handle)
    def active(self):
        class Accounting(ctypes.Structure): _fields_=[("User",ctypes.c_longlong),("Kernel",ctypes.c_longlong),("PeriodUser",ctypes.c_longlong),("PeriodKernel",ctypes.c_longlong),("Faults",wintypes.DWORD),("Total",wintypes.DWORD),("Active",wintypes.DWORD),("Terminated",wintypes.DWORD)]
        info=Accounting()
        if not self.api.QueryInformationJobObject(self.handle,1,ctypes.byref(info),ctypes.sizeof(info),None): raise ctypes.WinError(ctypes.get_last_error())
        return info.Active
    def stop(self):
        if not self.api.TerminateJobObject(self.handle,1): raise ctypes.WinError(ctypes.get_last_error())
    def close(self):
        if self.handle:
            handle,self.handle=self.handle,None
            if not self.api.CloseHandle(handle): raise ctypes.WinError(ctypes.get_last_error())

def observe_worker(root,state,record,*,worker_running,failure=False):
    """Best-effort console evidence only; never change the worker or gate result."""
    view={"worker_running":worker_running,"observed_at":stamp()}
    last={}; report={}
    try:
        path=state/"windows-development.json"; checked(path)
        with path.open("rb") as source: raw=source.read(4*1024**2+1)
        need(len(raw)<=4*1024**2,"worker_observation_oversized")
        loaded=json.loads(raw.decode("utf-8")); need(isinstance(loaded,dict),"worker_observation_not_object"); report=loaded
        stage=report.get("failed_stage")
        if stage is None:
            stage=next((name for name in ("build","check") if report.get(name,{}).get("status")=="running"),"complete" if report.get("status")=="passed_check_and_build_only" else "prepare")
        view.update(stage=stage,status=report.get("status"),check_status=report.get("check",{}).get("status"),build_status=report.get("build",{}).get("status"))
        steps=report.get("steps",[])
        if isinstance(steps,list) and steps and isinstance(steps[-1],dict):
            last=steps[-1]
            view["last_step"]={"label":str(last.get("label",""))[:160],"exit_code":last.get("exit_code"),"error_type":last.get("error_type")}
    except Exception as error: view["observation_error"]=type(error).__name__
    if failure:
        view.update(error_type=report.get("error_type") or record.get("error") or record.get("cleanup_error"),error=str(report.get("error") or record.get("message") or "")[:1000])
        try:
            selected=pathlib.Path(last["log"]) if last.get("log") and (last.get("error_type") or last.get("exit_code") not in (None,0)) else state/"failure.log"
            if not selected.exists(): selected=state/"controller-worker.log"
            checked(selected)
            need(selected.is_relative_to(state) or selected.is_relative_to(root/"app/build/outputs/apk/preview"),"worker_log_outside_owned_paths")
            with selected.open("rb") as source:
                source.seek(max(0,selected.stat().st_size-8192)); tail=source.read(8192)
            view.update(log_name=selected.name,log_tail_bytes=len(tail),log_tail=tail.decode("utf-8",errors="replace"))
        except Exception as error: view["log_observation_error"]=type(error).__name__
    try: print(("WINDOWS_DEVELOPMENT_FAILURE=" if failure else "WINDOWS_DEVELOPMENT_PROGRESS=")+json.dumps(view),flush=True)
    except Exception: pass  # Console observation cannot replace a check or cleanup result.

def control(root,state,manifest):
    need(not state.exists(),"owned_state_already_exists"); state.mkdir()
    metadata={"schema":1,"kind":"windows_development_check_build","origin":"Windows laptop","host":"LAPTOP-NPSGA016","base_commit":BASE_COMMIT,"base_source_sha256":BASE_SOURCE,
        "github":{"run_id":int(os.environ["GITHUB_RUN_ID"]),"run_attempt":int(os.environ["GITHUB_RUN_ATTEMPT"]),"workflow_sha":os.environ["GITHUB_WORKFLOW_SHA"],"runner_name":os.environ["RUNNER_NAME"]},
        "status":"preparing","started_at":stamp(),"steps":[],"check":{"status":"not_run"},"build":{"status":"not_run"},"runtime":{"status":"not_run"},"publication_authorized":False,"phone_verified":False,"timeweb_execution":False,"root":str(root),"state":str(state),"bootstrap_sha256":sha(pathlib.Path(__file__).resolve()),"patch_manifest_sha256":sha(manifest),"python_version":sys.version.split()[0],"external_quality_gate":{"status":"not_run_by_this_bootstrap"},
        "retention":{"owned_checkout":str(root),"owned_state":str(state),"automatic_deletion_performed":False,"cleanup_requires":["exact_private_archive_confirmed_on_Timeweb","exact_source_inventory_backed_up_in_Git","required_APK_inputs_retained_for_runtime_and_phone"],"preserve_shared_sdk_gradle_signing_profile":True}}
    save(state/"windows-development.json",metadata)
    checked(root/".github/scripts/emulator_lease.py")
    need(git_blob((root/".github/scripts/emulator_lease.py").read_bytes())==LEASE_BLOB,"emulator_lease_source_changed")
    sys.path.insert(0,str(root/".github/scripts")); import emulator_lease as lease
    directory=pathlib.Path(tempfile.gettempdir()).resolve()/"analyst-ai-emulator-lease"
    directory.mkdir(exist_ok=True); lease._reject_link(directory)
    record={"started_at":stamp(),"lease":str(directory/"android.lock"),"worker_started":False,"owned_processes_after":None,"error":None}
    job=None; process=None; acquired=False; context=lease._lease_at_path(directory/"android.lock",1200)
    try:
        context.__enter__(); acquired=True
        record["lease_acquired_at"]=stamp(); job=OwnedJob()
        with (state/"controller-worker.log").open("xb") as out:
            process=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).resolve()),"worker","--manifest",str(manifest)],cwd=root,stdin=subprocess.PIPE,stdout=out,stderr=subprocess.STDOUT,close_fds=True)
            job.attach(process); record["worker_started"]=True; record["worker_pid"]=process.pid
            process.stdin.write(b"WINDOWS_OWNED_JOB_READY\n"); process.stdin.close()
            deadline=time.monotonic()+MAX_WORK_SECONDS
            while process.poll() is None:
                need(time.monotonic()<deadline,"windows_work_deadline_exceeded")
                try: process.wait(timeout=min(30,max(0.1,deadline-time.monotonic())))
                except subprocess.TimeoutExpired: pass
                observe_worker(root,state,record,worker_running=process.poll() is None)
            record["worker_exit_code"]=process.returncode
        end=time.monotonic()+30
        while job.active() and time.monotonic()<end: time.sleep(0.2)
        record["remaining_before_cleanup"]=job.active()
        need(process.returncode==0,"windows_worker_failed")
    except BaseException as error:
        record["error"]=type(error).__name__; record["message"]=str(error)[:300]; raise
    finally:
        cleanup_error=None
        try:
            if job is not None:
                try:
                    if job.active(): job.stop()
                    end=time.monotonic()+30
                    while job.active() and time.monotonic()<end: time.sleep(0.2)
                    record["owned_processes_after"]=job.active()
                    need(record["owned_processes_after"]==0,"owned_worker_processes_remain")
                finally: job.close()
            if process is not None and process.poll() is None:
                process.kill(); process.wait(timeout=15)
        except BaseException as error:
            cleanup_error=error; record["cleanup_error"]=type(error).__name__
        finally:
            record["finished_at"]=stamp()
            try: save(state/"controller.json",record)
            finally:
                if acquired: context.__exit__(None,None,None)
            print("WINDOWS_DEVELOPMENT_CONTROLLER="+json.dumps(record),flush=True)
            if record["error"] is not None or cleanup_error is not None: observe_worker(root,state,record,worker_running=process is not None and process.poll() is None,failure=True)
        if cleanup_error is not None and record["error"] is None: raise cleanup_error

def export(root,state):
    checked(state,True)
    report=json.loads((state/"windows-development.json").read_text(encoding="utf-8")); controller=json.loads((state/"controller.json").read_text(encoding="utf-8"))
    need(not controller.get("cleanup_error") and (controller.get("owned_processes_after")==0 or controller.get("worker_started") is False),"worker_not_stopped_for_export")
    final,files,complete_final=inventory(root,state)
    need(report.get("source_sha256_after",final)==final and report.get("complete_source_sha256_after",complete_final)==complete_final,"source_changed_after_worker")
    entries={}
    def add(relative,path):
        need(relative not in entries,"duplicate_export_path"); info=checked(path)
        need(info.st_size<=128*1024**2,"oversized_evidence_file")
        entries[relative]=(path,{"bytes":info.st_size,"sha256":sha(path)})
    for name in files: add("source/"+name,root/name)
    for path in sorted(state.iterdir()):
        if path.is_file() and path.suffix in (".json",".log",".xml"): add("evidence/"+path.name,path)
    trees=("app/build/reports","app/build/test-results","ci-ui-driver/build/reports","ci-ui-driver/build/test-results")
    for relative in trees:
        base=root/relative
        if not base.exists(): continue
        for directory,dirs,names in os.walk(base,followlinks=False):
            checked(pathlib.Path(directory),True)
            for name in names:
                path=pathlib.Path(directory)/name
                if path.suffix.lower() in (".json",".xml",".txt",".html",".css",".js",".sarif"): add("reports/"+path.relative_to(root).as_posix(),path)
    outputs=("app/build/outputs/apk/debug/app-debug.apk","app/build/outputs/apk/preview/app-preview.apk","app/build/outputs/apk/release/app-release-unsigned.apk","ci-ui-driver/build/outputs/apk/debug/ci-ui-driver-debug.apk")
    for relative in outputs:
        path=root/relative
        if path.exists(): add("outputs/"+relative,path)
    for name in ("signature.txt","alignment.txt","badging.txt","manifest.txt","apk-verification.json","native-alignment.json"):
        path=root/"app/build/outputs/apk/preview"/name
        if path.exists(): add("outputs/app/build/outputs/apk/preview/"+name,path)
    need(sum(value[1]["bytes"] for value in entries.values())<490*1024**2,"evidence_export_size_bound")
    envelope={"schema":1,"kind":"windows_check_build_source_archive","source_sha256":final,"complete_source_sha256":complete_final,"base_commit":BASE_COMMIT,"report":report,"controller":controller,
        "files":{name:value[1] for name,value in entries.items()},"runtime_pass":False,"publication_authorized":False,"phone_verified":False,"created_at":stamp()}
    destination=pathlib.Path(os.environ["RUNNER_TEMP"])/"ci-handoff.zip"; need(not destination.exists(),"handoff_file_already_exists")
    partial=state/"development-evidence.zip.partial"
    with zipfile.ZipFile(partial,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=3) as archive:
        for name,(path,identity) in sorted(entries.items()):
            data=path.read_bytes(); need(len(data)==identity["bytes"] and digest(data)==identity["sha256"],"evidence_changed_during_export")
            archive.writestr(name,data)
        archive.writestr("windows-development-envelope.json",json.dumps(envelope,sort_keys=True))
    need(partial.stat().st_size<=MAX_ARCHIVE,"compressed_archive_too_large")
    after=inventory(root,state); need(after[0]==final and after[2]==complete_final,"source_changed_during_export")
    os.replace(partial,destination)
    receipt={"bytes":destination.stat().st_size,"sha256":sha(destination),"files":len(entries),"source_sha256":final,"complete_source_sha256":complete_final,"status":report["status"],"runtime_pass":False,"publication_authorized":False}
    save(state/"export-receipt.json",receipt); print("WINDOWS_DEVELOPMENT_EXPORT="+json.dumps(receipt),flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("stage",choices=("control","worker","export")); parser.add_argument("--manifest",type=pathlib.Path); args=parser.parse_args()
    if args.stage=="worker": need(sys.stdin.buffer.readline(64)==b"WINDOWS_OWNED_JOB_READY\n","worker_job_handshake_missing")
    ROOT,STATE,_,_=paths()
    if args.stage=="control": need(args.manifest is not None,"manifest_required"); control(ROOT,STATE,args.manifest.resolve(strict=True))
    elif args.stage=="worker": worker(ROOT,STATE,args.manifest.resolve(strict=True))
    else: export(ROOT,STATE)
