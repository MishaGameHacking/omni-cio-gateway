"""Prepare bounded native navigation45 only from completed Windows evidence.

Administrative source generation only. This script imports one hash-pinned
administrative generator; it never imports or executes application/test code.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re

import yaml

CONTEXT = Path(__file__).resolve().parent
TARGET = ".github/workflows/windows-n00-navigation45.yml"
BASE_COMMIT = "1cc05586b6874bfdd0cdb80131d178de9f95870c"
BASE_SOURCE = "e34b717fa408fbe377d910a372933c35a2ba1bdddf02263b6daa477df70f93b9"
PREVIOUS_SHA = "f0af0b45515143f8abb2c28e73d0d484acde5c6a36e18de1b398692bc45a4cf6"
PREVIOUS_BYTES = 29771254
PREVIOUS_ROOT = r"C:\actions-runner-3\_work\omni-cio-gateway\omni-cio-gateway\windows-development-40282775349-1"
CERTIFICATE = "bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1"
PINS = {
    "prepare_native44.py": "f3f1321d3f3e5d8c0f2244b932fe055b29953abc4e202af0bb982ab3d8e32dc2",
    "native44-bound/n00-runtime.py": "b5479dcb488eed6e38a1c2dc40d21b43e6ce61aeeaed644037be169e4d0d0cb9",
    "native44-bound/workflow.yml": "9ee2325a8746d5123d0ae07792195639b50f1e738f9f10466fa1c59d04e391d8",
}
APK_PATHS = ("app/build/outputs/apk/preview/app-preview.apk",
             "app/build/outputs/apk/debug/app-debug.apk",
             "ci-ui-driver/build/outputs/apk/debug/ci-ui-driver-debug.apk")


def need(value, message):
    if not value:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def decode(raw):
    def unique(pairs):
        result = {}
        for name, value in pairs:
            need(name not in result, "Duplicate JSON key")
            result[name] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique)
    need(type(value) is dict, "JSON object required")
    return value


def checked(path, expected):
    need(isinstance(expected, str) and re.fullmatch(r"[a-f0-9]{64}", expected), "SHA256 required")
    path = path.absolute()
    need(CONTEXT in path.parents and path.is_file() and not path.is_symlink()
         and path.resolve(strict=True) == path, "Input must be an existing canonical context file")
    before = path.stat()
    need(before.st_nlink == 1 and 0 < before.st_size <= 8 * 1024**2, "Input outside size/link bounds")
    raw = path.read_bytes()
    after = path.stat()
    need((before.st_ino, before.st_size, before.st_mtime_ns) ==
         (after.st_ino, after.st_size, after.st_mtime_ns), "Input changed while reading")
    need(digest(raw) == expected, "Input differs from reviewed SHA256: " + path.name)
    return raw


def evidence(request, name):
    ref = request[name]
    need(type(ref) is dict and set(ref) == {"path", "sha256"}, "Invalid evidence reference")
    path = PurePosixPath(ref["path"])
    need(not path.is_absolute() and path.parts[0] == "context" and ".." not in path.parts
         and path.as_posix() == ref["path"] and "\\" not in ref["path"], "Invalid evidence path")
    raw = checked(CONTEXT.parent / path, ref["sha256"])
    return decode(raw), raw


def pinned(name):
    return checked(CONTEXT / name, PINS[name])


def helpers():
    pinned("prepare_native44.py")
    spec = importlib.util.spec_from_file_location("administrative_native44", CONTEXT / "prepare_native44.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def literal(text, name):
    values = [node.value for node in ast.parse(text).body if isinstance(node, ast.Assign)
              and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
              and node.targets[0].id == name]
    need(len(values) == 1, "Missing template assignment: " + name)
    return ast.literal_eval(values[0])


def validate(request):
    need(set(request) == {"schema", "source_backup_commit", "source_sha256", "build_report",
        "build_controller", "build_export_receipt", "source_inventory", "reviewed_manifest",
        "prepared_build", "baseline_publication"}, "Unexpected request fields")
    need(request["schema"] == 1 and re.fullmatch(r"[a-f0-9]{40}", request["source_backup_commit"])
         and request["source_backup_commit"] != BASE_COMMIT and
         re.fullmatch(r"[a-f0-9]{64}", request["source_sha256"]), "Actual source45 backup is required")
    report, report_raw = evidence(request, "build_report")
    controller, _ = evidence(request, "build_controller")
    exported, export_raw = evidence(request, "build_export_receipt")
    inventory, _ = evidence(request, "source_inventory")
    reviewed, _ = evidence(request, "reviewed_manifest")
    prepared, _ = evidence(request, "prepared_build")
    publication, publication_raw = evidence(request, "baseline_publication")
    source = request["source_sha256"]
    need(report["schema"] == 1 and report["kind"] == "windows_development_check_build"
         and report["host"] == "LAPTOP-NPSGA016" and report["origin"] == "Windows laptop"
         and report["base_commit"] == BASE_COMMIT and report["base_source_sha256"] == BASE_SOURCE,
         "Build45 must start from the verified44 source backup")
    need(report["status"] == "passed_check_and_build_only"
         and report["check"]["status"] == report["build"]["status"] == "passed"
         and all(value == source for value in (report["source_sha256"], report["source_sha256_after"],
             report["check"]["source_sha256"], report["build"]["source_sha256"])),
         "Complete successful unchanged Windows build45 is required")
    complete = report["complete_source_sha256"]
    need(report["complete_source_sha256_after"] == complete and report["certificate_sha256"] == CERTIFICATE
         and all(report[key] is False for key in ("publication_authorized", "phone_verified", "timeweb_execution"))
         and report["runtime"]["status"] == "not_run", "Build45 scope/signature changed")
    steps = report["steps"]
    labels = [row["label"] for row in steps]
    need(len(set(labels)) == len(labels) and
         {"host-tests", "tools-tests", "node-tests", "backend-tests", "gradle", "apk-verification"} <= set(labels)
         and all(type(row["exit_code"]) is int and row["exit_code"] == 0 for row in steps),
         "A full build45 phase is missing or failed")
    need(controller["worker_started"] is True and controller["worker_exit_code"] == 0
         and controller["owned_processes_after"] == 0 and controller.get("finished_at")
         and controller.get("lease_acquired_at") and not controller.get("error")
         and not controller.get("cleanup_error"), "Build45 worker/cleanup incomplete")
    need(PureWindowsPath(controller["lease"]) == PureWindowsPath(
        "C:/Windows/ServiceProfiles/NetworkService/AppData/Local/Temp/analyst-ai-emulator-lease/android.lock"),
        "Canonical build lease changed")
    need(exported["status"] == "passed_check_and_build_only"
         and exported["source_sha256"] == source and exported["complete_source_sha256"] == complete
         and exported["runtime_pass"] is False and exported["publication_authorized"] is False
         and type(exported["bytes"]) is int and 0 < exported["bytes"] <= 256 * 1024**2
         and re.fullmatch(r"[a-f0-9]{64}", exported["sha256"]), "Build45 archive evidence differs")
    need(prepared["base_commit"] == BASE_COMMIT and prepared["base_source_sha256"] == BASE_SOURCE
         and prepared["bootstrap_sha256"] == report["bootstrap_sha256"]
         and prepared["patch_manifest_sha256"] == report["patch_manifest_sha256"]
         and prepared["reviewed_files_sha256"] == request["reviewed_manifest"]["sha256"],
         "Build45 does not match its reviewed transport")
    need(reviewed["schema"] == 1 and reviewed["version_before"] == {"code": 44, "name": "0.13.6"}
         and reviewed["version_after"] == {"code": 45, "name": "0.13.7"},
         "Reviewed source is not the exact version45 candidate")
    rows = {row["path"]: row for row in reviewed["files"]}
    need(len(rows) == len(reviewed["files"]) == 29 and set(rows) == {'.github/scripts/automation_ui_probe.py', '.github/scripts/navigation_detail_probe.py', '.github/scripts/persistent_ui.py', '.github/scripts/profile_scroll.py', '.github/scripts/tests/fixtures/NavigationBackFixtureTest.java', '.github/scripts/tests/test_android17_live_spectrum.py', '.github/scripts/tests/test_automation_error_visibility.py', '.github/scripts/tests/test_automation_ui_probe.py', '.github/scripts/tests/test_navigation_back_progress.py', '.github/scripts/tests/test_navigation_detail_probe.py', '.github/scripts/tests/test_navigation_return_scroll.py', '.github/scripts/tests/test_portfolio_semantic_scroll.py', '.github/scripts/tests/test_predictive_back_input.py', '.github/scripts/tests/test_profile_scroll.py', '.github/scripts/tests/test_spectrum_brand_identity.py', '.github/scripts/tests/test_strategy_horizon.py', 'app/build.gradle.kts', 'app/src/debug/java/ru/omnicio/app/AutomationWorkspaceProbe.kt', 'app/src/debug/java/ru/omnicio/app/BusinessWorkspaceProbe.kt', 'app/src/main/java/ru/omnicio/app/MainActivity.kt', 'app/src/main/java/ru/omnicio/app/ui/AnalystBottomBar.kt', 'app/src/main/java/ru/omnicio/app/ui/AnalystNavigationPanels.kt', 'app/src/main/java/ru/omnicio/app/ui/workspace/AppearanceScreen.kt', 'app/src/main/java/ru/omnicio/app/ui/workspace/LiveStrategyScreen.kt', 'app/src/main/java/ru/omnicio/app/ui/workspace/WorkspaceUi.kt', 'app/src/test/java/ru/omnicio/app/ui/PanelNavigationGuardTest.kt', 'ci-ui-driver/src/main/java/ru/omnicio/ciframe/BackGestureInput.java', 'ci-ui-driver/src/main/java/ru/omnicio/ciframe/FrameInstrumentation.java', 'ci-ui-driver/src/main/java/ru/omnicio/ciframe/NavigationBackFixture.java'}
         and source == "c7db1ac10f4dca90d57bf740bd57a9dfe6ef44002f2de0593cfa3d755f0512fd"
         and report["github"]["run_id"] == 40334863828, "Unexpected exact fitted-capture45 source scope")
    patches = {row["path"]: row for row in report["patch_files"]}
    need(len(patches) == len(report["patch_files"]) and set(patches) == set(rows),
         "Windows-applied45 source scope differs")
    need(set(inventory) == {"files", "source_sha256", "complete_source_sha256"}, "Wrong original inventory schema")
    code_digest, complete_digest = hashlib.sha256(), hashlib.sha256()
    seen = set()
    for name, identity in sorted(inventory["files"].items(), key=lambda row: row[0].encode()):
        p = PurePosixPath(name)
        need(p.as_posix() == name and not p.is_absolute() and ".." not in p.parts and "\\" not in name
             and name.casefold() not in seen and "\0" not in name and "\n" not in name,
             "Unsafe source inventory path")
        seen.add(name.casefold())
        need(set(identity) == {"bytes", "sha256"} and type(identity["bytes"]) is int and identity["bytes"] >= 0
             and re.fullmatch(r"[a-f0-9]{64}", identity["sha256"]), "Invalid inventory identity")
        record = name.encode() + b"\0" + identity["sha256"].encode() + b"\0"
        complete_digest.update(record)
        if name not in ("AGENTS.md", "README.md") and not name.startswith("docs/"):
            code_digest.update(record)
    need(code_digest.hexdigest() == source == inventory["source_sha256"]
         and complete_digest.hexdigest() == complete == inventory["complete_source_sha256"],
         "Actual build45 source inventory digest differs")
    for name, row in rows.items():
        raw = row["content"].encode()
        need(len(raw) == row["new_bytes"] and digest(raw) == row["new_sha256"]
             and patches[name]["old_sha256"] == row["old_sha256"]
             and patches[name]["new_sha256"] == row["new_sha256"]
             and inventory["files"][name] == {"bytes": len(raw), "sha256": digest(raw)},
             "Windows45 source identity differs: " + name)
    source_evidence = literal(pinned("native44-bound/n00-runtime.py").decode(), "SOURCE_EVIDENCE")
    for name in source_evidence:
        if name not in rows:
            need(inventory["files"].get(name) == source_evidence[name], "Earlier44 repair changed: " + name)
    for name in rows:
        source_evidence[name] = inventory["files"][name]
    previous = publication["publication"]
    need(publication["https_policy_verified"] is True and publication["https_entire_apk_download_verified"] is True
         and publication["https_apk_bytes"] == PREVIOUS_BYTES and publication["https_apk_sha256"] == PREVIOUS_SHA
         and publication["backend_health_http"] == 200 and previous["version_code"] == previous["channel_version"] == 44
         and previous["version_name"] == "0.13.6-preview" and previous["apk_sha256"] == PREVIOUS_SHA
         and previous["apk_bytes"] == PREVIOUS_BYTES and previous["package_name"] == "ru.omnicio.app.debug"
         and previous["certificate_sha256"] == CERTIFICATE and previous["source_backup_commit"] == BASE_COMMIT
         and previous["source_sha256"] == BASE_SOURCE and previous["windows_run_id"] == 40282775349,
         "Baseline must be the actually published and HTTPS-verified44")
    github = report["github"]
    run, attempt = github["run_id"], github["run_attempt"]
    need(type(run) is int and run > 0 and type(attempt) is int and 0 < attempt < 100000
         and re.fullmatch(r"[a-f0-9]{40}", github["workflow_sha"]), "Invalid build45 run")
    root = PureWindowsPath(report["root"])
    need(len(root.parts) == 6 and root.drive.upper() == "C:"
         and root.parts[1] in ("actions-runner", "actions-runner-2", "actions-runner-3", "actions-runner-4")
         and root.parts[2:] == ("_work", "omni-cio-gateway", "omni-cio-gateway", f"windows-development-{run}-{attempt}"),
         "Build45 root is not run-owned")
    need(PureWindowsPath(report["state"]) == root.parents[2] / "_temp" / f"analyst-development-{run}-{attempt}",
         "Build45 state is not run-owned")
    files = {}
    for name in APK_PATHS:
        value = report["apks"][name]
        need(set(value) == {"bytes", "sha256"} and type(value["bytes"]) is int and 0 < value["bytes"] < 256 * 1024**2
             and re.fullmatch(r"[a-f0-9]{64}", value["sha256"]), "Invalid built APK45 identity")
        files[name] = [value["bytes"], value["sha256"]]
    need(files[APK_PATHS[0]][1] == report["build"]["apk_sha256"] != PREVIOUS_SHA, "Preview45 reused44 bytes")
    provenance = {
        "build_report_sha256": digest(report_raw), "build_run_id": run, "build_run_attempt": attempt,
        "build_workflow_sha": github["workflow_sha"], "build_status": report["status"], "host": "LAPTOP-NPSGA016",
        "root": str(root), "state": report["state"], "build_base_commit": BASE_COMMIT,
        "source_backup_commit": request["source_backup_commit"], "source_sha256": source,
        "complete_build_source_sha256": complete, "build_export_receipt_sha256": digest(export_raw),
        "build_archive": {"bytes": exported["bytes"], "sha256": exported["sha256"]},
        "preview_version_code": 45, "preview_version_name": "0.13.7-preview",
        "input_apks": files, "candidate_source_files": source_evidence,
        "baseline": {"version_code": 44, "version_name": "0.13.6-preview", "bytes": PREVIOUS_BYTES,
                     "sha256": PREVIOUS_SHA, "retained_build_run_id": 40282775349,
                     "publication_receipt_sha256": digest(publication_raw), "published_at": previous["published_at"]},
        "navigation_required": {"automation": 26, "panels": 4, "detail": 2, "wide": 2},
        "original_portfolio_cases_required": 14, "original_portfolio_executed": False,
        "full_ui_stage_count": 15, "diagnostic_only": True, "release_gate_pass": False,
        "full_ui_suite_executed": False, "publication_authorized": False, "phone_verified": False,
    }
    return files, source_evidence, provenance, report_raw, export_raw


HOOK = '''"""Observe real navigation45; preserve the unchanged full-suite gate."""
import hashlib,json,sys,xml.etree.ElementTree as ET
from pathlib import Path
import profile_ui_probe as module
from automation_ui_probe import exercise_automation
from profile_snapshot import restore_device_settings
def focused(device,read_tree):
    probe=module.ProfileProbe(device);probe.read_tree=read_tree
    night=module.night_setting(probe.command('shell','cmd','uimode','night'))
    scale=probe.command('shell','settings','get','system','font_scale').strip()
    report={'diagnostic_only':True,'release_gate_pass':False,'navigation_complete':False,
            'original_portfolio_executed':False,'full15_executed':False}
    folder=Path(module.__file__).resolve().parents[2]/'app/build/outputs/apk/preview/ui-screens'
    try:
        result=exercise_automation(probe)
        evidence={}
        expected={'automation-verification.json':26,'navigation-panels-verification.json':4,
                  'navigation-detail-verification.json':2,'navigation-wide-verification.json':2}
        for name,count in expected.items():
            path=folder/name
            if path.is_symlink() or not path.is_file():raise AssertionError('Missing owned navigation evidence')
            raw=path.read_bytes();value=json.loads(raw)
            if value.get('schema_version')!=1 or len(value.get('cases',[]))!=count:
                raise AssertionError('Incomplete original navigation cases: '+name)
            if value.get('fixture_apk_sha256')!=result['fixture_apk_sha256']:
                raise AssertionError('Navigation receipt APK changed')
            if name in ('navigation-detail-verification.json','navigation-wide-verification.json'):
                if value.get('status')!='passed' or {row['font_scale'] for row in value['cases']}!={1.0,2.0}:
                    raise AssertionError('Detail or wide native observation incomplete')
            if name=='navigation-wide-verification.json' and value.get('viewport',{}).get('restored') is not True:
                raise AssertionError('Wide viewport was not restored')
            evidence[name]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'case_count':count}
        report.update(navigation_complete=True,evidence=evidence)
        raise AssertionError('Diagnostic only: full UI suite was deliberately not claimed')
    except BaseException as error:
        report.update(error_type=type(error).__name__,error=str(error)[:1000])
        if not report['navigation_complete']:
            try:
                folder.mkdir(parents=True,exist_ok=True)
                probe.capture('navigation-focused-failure')
                (folder/'navigation-focused-failure.xml').write_text(ET.tostring(probe.tree(),encoding='unicode'),encoding='utf-8')
            except Exception as capture_error:report['failure_capture_error']=type(capture_error).__name__
        raise
    finally:
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'navigation-focused-observations.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('NAVIGATION_FOCUSED_OBSERVATIONS='+json.dumps(report),flush=True)
        restore_device_settings(probe.command,scale,night,sys.exc_info()[1])
module.exercise_checks=focused
'''


def render(files, source_evidence, provenance, report_raw, export_raw):
    helper = helpers()
    original = pinned("native44-bound/n00-runtime.py").decode()
    runtime = original
    for name, value in (("BASE_COMMIT", provenance["source_backup_commit"]), ("SOURCE_HASH", provenance["source_sha256"]),
                        ("SOURCE_EVIDENCE", source_evidence), ("BUILD_PROVENANCE", provenance), ("FILES", files)):
        runtime = helper.assignment(runtime, name, value)
    runtime = helper.replace_once(runtime, "PREVIOUS_HASH='4e9bf0a2fd54d8ab4b9d49ef9ddf96bc14a274ac4c145585fcfdb88d6ae774b6'",
                                  "PREVIOUS_HASH=" + repr(PREVIOUS_SHA))
    line = next(line for line in runtime.splitlines() if line.startswith("BASELINE = "))
    runtime = helper.replace_once(runtime, line, "BASELINE = pathlib.Path(" +
                                  repr(str(PureWindowsPath(PREVIOUS_ROOT) / PureWindowsPath(APK_PATHS[0]))) + ")")
    replacements = (("n00-native44-focused-", "n00-native45-focused-"),
                    ("native44-build-provenance.json", "native45-build-provenance.json"),
                    ("native44-evidence-envelope.json", "native45-evidence-envelope.json"),
                    ("n00_candidate44_portfolio_focused", "n00_candidate45_navigation_focused"),
                    ("previous43.apk", "previous44.apk"), ("published_baseline43_changed", "published_baseline44_changed"),
                    ("n00-portfolio-focused-hook.py", "n00-navigation-focused-hook.py"))
    for old, new in replacements:
        need(old in runtime, "Native44 template anchor missing: " + old)
        runtime = runtime.replace(old, new)
    anchor = "'original_portfolio_cases_required':14,'full_ui_stage_count':15"
    runtime = helper.replace_once(runtime, anchor,
        "'original_portfolio_cases_required':14,'original_portfolio_executed':False,"
        "'navigation_required':BUILD_PROVENANCE['navigation_required'],'full_ui_stage_count':15")
    old_functions = {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(original).body
                     if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    new_functions = {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(runtime).body
                     if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    need(set(old_functions) == set(new_functions), "Native process function set changed")
    for name in old_functions.keys() - {"profile", "export", "prepare"}:
        need(old_functions[name] == new_functions[name], "Native ownership/environment helper changed: " + name)
    for name in ("profile", "prepare"):
        old = original.split("def " + name + "(", 1)[1].split("\ndef ", 1)[0]
        new = runtime.split("def " + name + "(", 1)[1].split("\ndef ", 1)[0]
        for before, after in reversed(replacements):
            new = new.replace(after, before)
        need(old == new, "Native process, SDK or lease logic changed: " + name)
    ast.parse(HOOK)
    original_workflow = yaml.safe_load(pinned("native44-bound/workflow.yml"))
    workflow = copy.deepcopy(original_workflow)
    workflow["name"] = "N00 candidate45 native navigation and dirty-exit observations"
    workflow["on"]["push"]["paths"] = [TARGET]
    workflow["concurrency"]["group"] = "analyst-n00-candidate45-navigation-focused"
    need(workflow["concurrency"]["cancel-in-progress"] is False, "Cancellation policy changed")
    job = workflow["jobs"]["develop"]
    need(job["timeout-minutes"] == 100 and job["runs-on"] == ["self-hosted", "Windows", "X64", "omni-cio-ci"],
         "Windows host/bounds changed")
    job["name"] = "Observe actual phone and wide navigation on exact candidate45"
    steps, staged = [], False
    for step in job["steps"]:
        if step.get("name", "").startswith("Stage verified focused transport "):
            if not staged:
                new_steps = [helper.stage("n00-runtime.py", runtime.encode()),
                    helper.stage("n00-navigation-focused-hook.py", HOOK.encode()),
                    helper.stage("n00-successful-build-report.json", report_raw),
                    helper.stage("n00-build-export-receipt.json", export_raw)]
                new_steps[-1]["id"] = "setup"
                steps.extend(new_steps); staged = True
            continue
        if step.get("uses", "").startswith("actions/checkout@"):
            need(step["with"]["ref"] == BASE_COMMIT and step["with"]["persist-credentials"] is False,
                 "Native checkout identity changed")
            step["with"]["ref"] = provenance["source_backup_commit"]
        if step.get("id") == "prepare":
            step["name"] = "Verify exact tested source45 and actually published baseline44"
        if step.get("id") == "focused_report":
            identity = {key: provenance[key] for key in ("source_sha256", "build_run_id", "build_run_attempt", "build_report_sha256")}
            identity["source_commit"] = provenance["source_backup_commit"]
            script = "const identity=" + json.dumps(identity, separators=(",", ":")) + ";\n" + SUMMARY_SCRIPT
            step["with"]["script"] = script
            step["name"] = "Report navigation observation separately from the full matrix"
        if step.get("uses", "").startswith("actions/upload-artifact@"):
            step["with"]["name"] = "n00-candidate45-navigation-native-16384"
            step["with"]["path"] = step["with"]["path"].replace("n00-native44-focused-", "n00-native45-focused-")
            step["name"] = "Retain genuine navigation diagnostic reports and synthetic captures"
        if step.get("name") == "Original portfolio cases at fonts100 and200 on Android37 16KB":
            step["name"] = "Original automation plus phone and wide navigation at fonts100 and200"
        need(not step.get("continue-on-error"), "Diagnostic failure must remain visible")
        steps.append(step)
    need(staged, "Missing staged runtime")
    job["steps"] = steps
    for name in ("preflight", "collect", "cleanup", "result"):
        need(workflow["jobs"][name] == original_workflow["jobs"][name], "Private9417611 transfer or result gate changed")
    outputs = {"n00-runtime.py": runtime.encode(), "n00-navigation-focused-hook.py": HOOK.encode(),
        "n00-successful-build-report.json": report_raw, "n00-build-export-receipt.json": export_raw,
        "build-provenance.json": encoded(provenance),
        "workflow.yml": yaml.safe_dump(workflow, allow_unicode=True, sort_keys=False, width=120).encode()}
    return outputs


SUMMARY_SCRIPT = r'''const fs=require('node:fs'),p=require('node:path'),crypto=require('node:crypto');
const folder=p.join(process.env.SOURCE_ROOT,'app/build/outputs/apk/preview/ui-screens');
const file=p.join(folder,'navigation-focused-observations.json');
const source=fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')):{error:'focused_report_missing'};
const required={'automation-verification.json':26,'navigation-panels-verification.json':4,'navigation-detail-verification.json':2,'navigation-wide-verification.json':2};
const observed={};
let complete=source.diagnostic_only===true && source.release_gate_pass===false && source.navigation_complete===true
  && source.original_portfolio_executed===false && source.full15_executed===false;
for (const [name,count] of Object.entries(required)) {
  const path=p.join(folder,name);
  if (!fs.existsSync(path)) { complete=false; observed[name]={missing:true}; continue; }
  const bytes=fs.readFileSync(path), value=JSON.parse(bytes.toString('utf8'));
  const hash=crypto.createHash('sha256').update(bytes).digest('hex');
  const actual=Array.isArray(value.cases)?value.cases.length:0;
  const proof=source.evidence && source.evidence[name];
  if (actual!==count || !proof || proof.bytes!==bytes.length || proof.sha256!==hash || proof.case_count!==count) complete=false;
  observed[name]={required_cases:count,observed_cases:actual,bytes:bytes.length,sha256:hash};
}
const report={...identity,diagnostic_only:true,release_gate_pass:false,
  navigation:{complete,required,observed},original14:{executed:false,accepted:false,required_cases:14},
  full15:{executed:false,accepted:false,required_stages:15},observations:source};
const state=p.join(process.env.RUNNER_TEMP,'n00-native45-focused-'+process.env.GITHUB_RUN_ID+'-'+process.env.GITHUB_RUN_ATTEMPT);
fs.writeFileSync(p.join(state,'native45-navigation-summary.json'),JSON.stringify(report,null,2)+'\n');
core.setOutput('navigation_complete',String(complete));
core.info('N00_NAVIGATION_COMPLETE='+String(complete));core.info('N00_FULL15_ACCEPTED=false');
const title=complete?'Navigation observations completed; full matrix remains pending':'Navigation observations incomplete; full matrix remains pending';
const fence=String.fromCharCode(96).repeat(3);
await github.rest.checks.create({...context.repo,name:'N00 candidate45 navigation observations (diagnostic only)',
  head_sha:context.sha,status:'completed',conclusion:'neutral',
  output:{title,summary:fence+'json\n'+JSON.stringify(report,null,2)+'\n'+fence}});
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    raw = checked(args.request, args.request_sha256)
    request = decode(raw)
    destination = args.output.absolute()
    need(CONTEXT in destination.parents and not destination.exists() and not destination.is_symlink()
         and destination.parent.resolve(strict=True) == destination.parent, "New canonical output folder required")
    values = validate(request)
    outputs = render(*values)
    receipt = {"schema": 1, "state": "prepared_only_no_execution", "target_workflow": TARGET,
        "request_sha256": digest(raw), "source_backup_commit": request["source_backup_commit"],
        "source_sha256": request["source_sha256"], "original14_executed": False, "full15_accepted": False,
        "application_or_test_execution": False, "publication_performed": False, "phone_verified": False,
        "files": {name: {"bytes": len(data), "sha256": digest(data)} for name, data in outputs.items()}}
    outputs["preparation.json"] = encoded(receipt)
    destination.mkdir()
    for name, data in outputs.items():
        with (destination / name).open("xb") as stream:
            stream.write(data)
    print(json.dumps({key: value for key, value in receipt.items() if key != "files"}))


if __name__ == "__main__":
    main()
