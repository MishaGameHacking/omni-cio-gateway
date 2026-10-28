#!/usr/bin/env python3
"""Publish only an unchanged APK with complete current-source runtime evidence."""
import datetime,hashlib,importlib.util,json,os,pathlib,shutil,sys,urllib.request

ROOT=pathlib.Path("/srv/analyst-ai/workspace")
STATE=pathlib.Path("/var/lib/analyst-ai-build")
BACKUP=pathlib.Path("/var/backups/analyst-ai")


def main():
    assert os.geteuid()==0,"root_required_for_publication"
    spec=importlib.util.spec_from_file_location("workspace",ROOT/"deploy/timeweb_workspace.py")
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    os.chdir(ROOT)
    d=m.source_hash()
    for stage in ("check","build","runtime"):
        m.previous(stage,d)
    out=ROOT/"app/build/outputs/apk/preview"
    apk=out/"app-preview.apk"
    report=json.loads((out/"apk-verification.json").read_text())
    assert report["sha256"]==m.sha(apk)==m.previous("runtime",d)["apk_sha256"]

    import zipfile,re
    with zipfile.ZipFile(apk) as z:
        dex=b"".join(z.read(n) for n in z.namelist()
                     if re.fullmatch(r"classes\d*\.dex",n))
    assert b"analyst-ai-2941515.twc1.net" in dex and b"backend-not-configured.invalid" not in dex

    sys.path.insert(0,"/opt/analyst-ai")
    from backend.release_publication import publish
    from backend.client_updates import ReleaseChannel

    root=m.PUBLIC_RELEASES
    directory=m.public_release_directory()
    current=ReleaseChannel(root).current(m.PREVIEW_PACKAGE)
    m.require_public_path(directory/current.filename)
    m.require_runtime_baseline(m.previous("runtime",d),current)
    assert report["version_code"]>current.version_code,"new_version_code_required"

    BACKUP.mkdir(mode=0o700,parents=True,exist_ok=True)
    shutil.copyfile(directory/"current.json",
                    BACKUP/("release-before-"+str(report["version_code"])+".json"))
    release=publish(root,apk,report,expected_certificate=m.CERT,
                    notes="Проверенное обновление приложения")

    # publish() sets its own APK/manifests to 0644; preserve the private lock
    # and unrelated files, and keep APK downloads readable by the DynamicUser.
    req=urllib.request.Request(
        m.HOST+"/client/update-policy?package_name="+release.package_name
        +"&version_code="+str(release.version_code))
    with urllib.request.urlopen(req,timeout=30) as response:
        assert response.status==200
    h=hashlib.sha256()
    with urllib.request.urlopen(m.HOST+"/client/apk/"+release.filename,timeout=60) as response:
        for block in iter(lambda:response.read(1048576),b""):
            h.update(block)
    assert h.hexdigest()==release.apk_sha256,"public_download_mismatch"
    print(json.dumps({"published":release.version_code,"sha256":release.apk_sha256,
                      "url":m.HOST+"/client/apk/"+release.filename}))


if __name__=="__main__":
    main()
