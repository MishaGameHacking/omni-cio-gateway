"""Prepare original14 plus finite theme46 evidence from completed Windows receipts.

Administrative preparation only. No application/test code is imported or run,
and no final workflow is rendered without the actual successful46 build,
verified45 source backup and actually published45 upgrade baseline.
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
TARGET = ".github/workflows/windows-n00-theme46.yml"
CERTIFICATE = "bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1"
PINS = {
    "prepare_native45_counter.py": "6b9a7a7787cb295243e726db48c9fa90ccf41124c9e0db1c6f0a16a8397197ed",
    "prepare_candidate46_counter.py": "d69db46e29d20ca680b85d4f6d936856fd28f2fa5346c374d1a948ce355c84f3",
    "native44-bound/n00-runtime.py": "b5479dcb488eed6e38a1c2dc40d21b43e6ce61aeeaed644037be169e4d0d0cb9",
    "native44-bound/workflow.yml": "9ee2325a8746d5123d0ae07792195639b50f1e738f9f10466fa1c59d04e391d8",
    "native43/n00-portfolio-focused-hook.py": "ddff3bb7c57670141b9e5f0ce02994fb0d8ed7748b781776a284460614f2276e",
}
PACKAGE_PINS = {
    "core": "2082541c1da162c0e63d966051cfe2d7d841b02c325f9d46160d5fdf5d0fa912",
    "assets": "a320b29b48f408945d9f446070a9ef126262e31c806a60fa4123d7367ae3fd50",
    "lifecycle": "11bff56200fc64e8b1a886861ec2739e0522740f192d9dd77536f4ef0f17a134",
    "quotes": "d128777f368d916c0689c9f6ab378c2cdc36d9eae730e78e9fa6a2be3acd56a3",
}
APK_PATHS = ("app/build/outputs/apk/preview/app-preview.apk",
             "app/build/outputs/apk/debug/app-debug.apk",
             "ci-ui-driver/build/outputs/apk/debug/ci-ui-driver-debug.apk")
UNCHANGED_NATIVE_PATHS = (
    ".github/scripts/portfolio_ui_probe.py", ".github/scripts/profile_launch.py",
    ".github/scripts/profile_scroll.py", ".github/scripts/profile_snapshot.py",
    ".github/scripts/test_apk_installation.py", ".github/scripts/persistent_ui.py",
    ".github/scripts/emulator_lease.py", ".github/scripts/prepare_android_sdk.py",
    "backend/android_runtime_contract.py",
)
WORKER_SECONDS = 5400
STEP_MINUTES = 120
JOB_MINUTES = 140


def need(value, message):
    if not value:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def checked(path, expected):
    need(isinstance(expected, str) and re.fullmatch(r"[a-f0-9]{64}", expected), "SHA256 required")
    path = Path(path).absolute()
    need(CONTEXT in path.parents and path.is_file() and not path.is_symlink()
         and path.resolve(strict=True) == path, "Canonical existing context file required")
    before = path.stat()
    need(before.st_nlink == 1 and 0 < before.st_size <= 8 * 1024**2, "Input size/link bounds exceeded")
    raw = path.read_bytes()
    after = path.stat()
    need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
         (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), "Input changed while reading")
    need(digest(raw) == expected, "Input differs from reviewed SHA256: " + path.name)
    return raw


def decode(raw):
    def unique(pairs):
        value = {}
        for name, item in pairs:
            need(name not in value, "Duplicate JSON key")
            value[name] = item
        return value
    value = json.loads(raw, object_pairs_hook=unique,
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Non-finite JSON number")))
    need(type(value) is dict, "JSON object required")
    return value


def evidence(spec):
    need(type(spec) is dict and set(spec) == {"path", "sha256"}, "Invalid evidence reference")
    name = spec["path"]
    need(isinstance(name, str), "Evidence path must be text")
    path = PurePosixPath(name)
    need(path.parts and path.parts[0] == "context" and not path.is_absolute()
         and path.as_posix() == name and ".." not in path.parts and "\\" not in name and ":" not in name,
         "Invalid context evidence path")
    raw = checked(CONTEXT.parent / path, spec["sha256"])
    return decode(raw), raw


def pinned(name):
    return checked(CONTEXT / name, PINS[name])


def administrative(name):
    pinned(name)
    spec = importlib.util.spec_from_file_location("administrative_theme46_" + Path(name).stem, CONTEXT / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inventory_identity(inventory):
    need(set(inventory) == {"files", "source_sha256", "complete_source_sha256"}, "Unexpected source inventory schema")
    need(type(inventory["files"]) is dict and inventory["files"], "Empty source inventory")
    code, complete, seen = hashlib.sha256(), hashlib.sha256(), set()
    for name, value in sorted(inventory["files"].items(), key=lambda row: row[0].encode()):
        path = PurePosixPath(name)
        need(path.parts and not path.is_absolute() and path.as_posix() == name and ".." not in path.parts
             and not any(char in name for char in ("\\", ":", "\0", "\n", "\r"))
             and name.casefold() not in seen, "Unsafe or duplicate source inventory path")
        seen.add(name.casefold())
        need(type(value) is dict and set(value) == {"bytes", "sha256"}
             and type(value["bytes"]) is int and value["bytes"] >= 0
             and re.fullmatch(r"[a-f0-9]{64}", value["sha256"]), "Invalid source inventory identity")
        row = name.encode() + b"\0" + value["sha256"].encode() + b"\0"
        complete.update(row)
        if name not in ("AGENTS.md", "README.md") and not name.startswith("docs/"):
            code.update(row)
    need(code.hexdigest() == inventory["source_sha256"] and complete.hexdigest() == inventory["complete_source_sha256"],
         "Actual source inventory digest differs")
    return code.hexdigest(), complete.hexdigest()


def validate(request):
    required = {"schema", "verified45_request", "source_backup_commit", "source_sha256", "build_report",
        "build_controller", "build_export_receipt", "source_inventory", "reviewed_manifest", "prepared_build",
        "baseline_publication"}
    need(set(request) == required and request["schema"] == 1, "Unexpected native46 request fields")
    prior_request, _ = evidence(request["verified45_request"])
    native45 = administrative("prepare_native45_counter.py")
    prior_apks, prior_sources, prior, _, _ = native45.validate(prior_request)
    prior_inventory, _ = evidence(prior_request["source_inventory"])
    base, base_source = prior_request["source_backup_commit"], prior_request["source_sha256"]
    source, backup = request["source_sha256"], request["source_backup_commit"]
    need(re.fullmatch(r"[a-f0-9]{64}", source) and source != base_source
         and re.fullmatch(r"[a-f0-9]{40}", backup) and backup != base,
         "Actual successful46 source backup and code inventory are required")
    report, report_raw = evidence(request["build_report"])
    controller, controller_raw = evidence(request["build_controller"])
    exported, export_raw = evidence(request["build_export_receipt"])
    inventory, inventory_raw = evidence(request["source_inventory"])
    reviewed, _ = evidence(request["reviewed_manifest"])
    prepared, _ = evidence(request["prepared_build"])
    publication, publication_raw = evidence(request["baseline_publication"])
    actual_code, complete = inventory_identity(inventory)
    need(actual_code == source, "Actual46 source inventory differs from explicit input")
    need(report["schema"] == 1 and report["kind"] == "windows_development_check_build"
         and report["host"] == "LAPTOP-NPSGA016" and report["origin"] == "Windows laptop"
         and report["base_commit"] == base and report["base_source_sha256"] == base_source,
         "Build46 must start from the verified successful45 source backup")
    need(report["status"] == "passed_check_and_build_only"
         and report["check"]["status"] == report["build"]["status"] == "passed"
         and all(value == source for value in (report["source_sha256"], report["source_sha256_after"],
             report["check"]["source_sha256"], report["build"]["source_sha256"]))
         and report["complete_source_sha256"] == report["complete_source_sha256_after"] == complete,
         "Complete unchanged successful Windows build46 required")
    need(report["certificate_sha256"] == CERTIFICATE and report["runtime"]["status"] == "not_run"
         and all(report[key] is False for key in ("publication_authorized", "phone_verified", "timeweb_execution")),
         "Build46 signature or evidence scope changed")
    steps = report["steps"]
    labels = [row["label"] for row in steps]
    need(len(labels) == len(set(labels)) and
         {"host-tests", "tools-tests", "node-tests", "backend-tests", "gradle", "apk-verification"} <= set(labels)
         and all(type(row["exit_code"]) is int and row["exit_code"] == 0 for row in steps),
         "A complete full-build46 phase is missing or failed")
    need(controller["worker_started"] is True and controller["worker_exit_code"] == 0
         and controller["owned_processes_after"] == 0 and controller.get("finished_at")
         and controller.get("lease_acquired_at") and not controller.get("error") and not controller.get("cleanup_error")
         and PureWindowsPath(controller["lease"]) == PureWindowsPath(
             "C:/Windows/ServiceProfiles/NetworkService/AppData/Local/Temp/analyst-ai-emulator-lease/android.lock"),
         "Actual46 owned worker/lease cleanup is incomplete")
    need(exported["status"] == "passed_check_and_build_only" and exported["source_sha256"] == source
         and exported["complete_source_sha256"] == complete and exported["runtime_pass"] is False
         and exported["publication_authorized"] is False and type(exported["bytes"]) is int
         and 0 < exported["bytes"] <= 256 * 1024**2 and re.fullmatch(r"[a-f0-9]{64}", exported["sha256"]),
         "Actual46 archived build export differs")
    need(prepared["base_commit"] == base and prepared["base_source_sha256"] == base_source
         and prepared["base45_inventory_sha256"] == prior_request["source_inventory"]["sha256"]
         and prepared["base45_build_run"] == prior["build_run_id"]
         and prepared["bootstrap_sha256"] == report["bootstrap_sha256"]
         and prepared["patch_manifest_sha256"] == report["patch_manifest_sha256"]
         and prepared["reviewed_files_sha256"] == request["reviewed_manifest"]["sha256"]
         and prepared["version"] == {"code": 46, "name": "0.13.8"},
         "Actual46 build does not match its reviewed preparation")
    need(reviewed["schema"] == 1 and reviewed["kind"] == "reviewed_candidate46_themes_after_verified_windows45"
         and reviewed["version_before"] == {"code": 45, "name": "0.13.7"}
         and reviewed["version_after"] == {"code": 46, "name": "0.13.8"}
         and reviewed["base_commit"] == base and reviewed["base_source_sha256"] == base_source
         and reviewed["actual45_request"] == request["verified45_request"]
         and reviewed["package_manifests"] == prepared["package_manifests"], "Wrong reviewed46 union/base")

    # Reconstruct only the exact frozen source union and the three reviewed
    # version assertions. No rendering, application or dynamic source import.
    theme = administrative("prepare_candidate46_counter.py")
    packages = reviewed["package_manifests"]
    need(set(packages) == set(PACKAGE_PINS), "Missing frozen theme46 package")
    assembled, owners = {}, {}
    for kind in packages:
        need(packages[kind]["sha256"] == PACKAGE_PINS[kind], "A frozen46 source package changed: " + kind)
        for name, (raw, metadata) in theme.package_rows(kind, packages[kind]).items():
            need(name not in assembled, "Unreviewed package overlap")
            assembled[name], owners[name] = raw, kind
    prior_rows = {row["path"]: row for row in evidence(prior_request["reviewed_manifest"])[0]["files"]}
    need(theme.GRADLE not in assembled and theme.GRADLE in prior_rows, "Missing verified45 version source")
    assembled[theme.GRADLE] = prior_rows[theme.GRADLE]["content"].encode()
    need(digest(assembled[theme.GRADLE]) == prior_inventory["files"][theme.GRADLE]["sha256"],
         "Baseline45 Gradle bytes differ")
    owners[theme.GRADLE] = "version"
    for name, replacements in theme.VERSION_REPLACEMENTS.items():
        for old, new in replacements:
            need(assembled[name].count(old) == 1 and new not in assembled[name], "Reviewed46 version anchor changed")
            assembled[name] = assembled[name].replace(old, new, 1)
    rows = {row["path"]: row for row in reviewed["files"]}
    patches = {row["path"]: row for row in report["patch_files"]}
    need(len(assembled) == 68 and len(rows) == len(reviewed["files"]) == reviewed["source_file_count"] == 68
         and prepared["source_paths"] == 68 and set(rows) == set(assembled) == set(patches)
         and len(patches) == len(report["patch_files"]) and reviewed["file_owners"] == owners,
         "Windows46 scope differs from the exact reviewed68-file union")
    for name, row in rows.items():
        raw = row["content"].encode()
        before = prior_inventory["files"].get(name)
        need(raw == assembled[name] and digest(raw) == row["new_sha256"] and len(raw) == row["new_bytes"]
             and row["old_sha256"] == (before["sha256"] if before else None)
             and row["old_bytes"] == (before["bytes"] if before else None)
             and patches[name]["old_sha256"] == row["old_sha256"]
             and patches[name]["new_sha256"] == row["new_sha256"]
             and inventory["files"].get(name) == {"bytes": len(raw), "sha256": digest(raw)},
             "Actual Windows46 source identity differs: " + name)
    source_evidence = dict(prior_sources)
    for name in set(source_evidence) | set(UNCHANGED_NATIVE_PATHS):
        if name not in rows:
            need(inventory["files"].get(name) == prior_inventory["files"].get(name)
                 and name in prior_inventory["files"], "An inherited original native gate changed: " + name)
        source_evidence[name] = inventory["files"][name]
    source_evidence.update({name: inventory["files"][name] for name in rows})
    github = report["github"]
    run, attempt = github["run_id"], github["run_attempt"]
    need(type(run) is int and run > 0 and type(attempt) is int and 0 < attempt < 100000
         and re.fullmatch(r"[a-f0-9]{40}", github["workflow_sha"]), "Invalid actual46 build run")
    root = PureWindowsPath(report["root"])
    need(len(root.parts) == 6 and root.drive.upper() == "C:"
         and root.parts[1] in ("actions-runner", "actions-runner-2", "actions-runner-3", "actions-runner-4")
         and root.parts[2:] == ("_work", "omni-cio-gateway", "omni-cio-gateway", f"windows-development-{run}-{attempt}")
         and PureWindowsPath(report["state"]) == root.parents[2] / "_temp" / f"analyst-development-{run}-{attempt}",
         "Actual46 build root/state is not run-owned")
    files = {}
    for name in APK_PATHS:
        value = report["apks"][name]
        need(set(value) == {"bytes", "sha256"} and type(value["bytes"]) is int and 0 < value["bytes"] < 256 * 1024**2
             and re.fullmatch(r"[a-f0-9]{64}", value["sha256"]), "Invalid actual46 APK identity")
        files[name] = [value["bytes"], value["sha256"]]
    need(files[APK_PATHS[0]][1] == report["build"]["apk_sha256"] != prior_apks[APK_PATHS[0]][1],
         "Candidate46 preview reused45 bytes")
    previous = publication["publication"]
    old_bytes, old_sha = prior_apks[APK_PATHS[0]]
    need(publication["https_policy_verified"] is True and publication["https_entire_apk_download_verified"] is True
         and publication["https_apk_bytes"] == old_bytes and publication["https_apk_sha256"] == old_sha
         and publication["backend_health_http"] == 200 and previous["version_code"] == previous["channel_version"] == 45
         and previous["version_name"] == "0.13.7-preview" and previous["apk_bytes"] == old_bytes
         and previous["apk_sha256"] == old_sha and previous["package_name"] == "ru.omnicio.app.debug"
         and previous["certificate_sha256"] == CERTIFICATE and previous["source_backup_commit"] == base
         and previous["source_sha256"] == base_source and previous["windows_run_id"] == prior["build_run_id"]
         and previous["windows_run_attempt"] == prior["build_run_attempt"]
         and previous["build_report_sha256"] == prior["build_report_sha256"]
         and previous["build_export_receipt_sha256"] == prior["build_export_receipt_sha256"]
         and type(previous["published_at"]) is int and previous["published_at"] > 0,
         "Upgrade baseline must be the actually published and HTTPS-verified exact45 build")
    provenance = {
        "build_report_sha256": digest(report_raw), "build_controller_sha256": digest(controller_raw),
        "build_run_id": run, "build_run_attempt": attempt, "build_workflow_sha": github["workflow_sha"],
        "build_status": report["status"], "host": "LAPTOP-NPSGA016", "root": str(root), "state": report["state"],
        "build_base_commit": base, "build_base_source_sha256": base_source,
        "source_backup_commit": backup, "source_sha256": source, "complete_build_source_sha256": complete,
        "build_source_inventory_receipt_sha256": digest(inventory_raw),
        "build_export_receipt_sha256": digest(export_raw),
        "build_archive": {"bytes": exported["bytes"], "sha256": exported["sha256"]},
        "reviewed_union_sha256": request["reviewed_manifest"]["sha256"], "frozen_package_sha256": PACKAGE_PINS,
        "preview_version_code": 46, "preview_version_name": "0.13.8-preview",
        "debug_version_code": 46, "debug_version_name": "0.13.8-debug",
        "input_apks": files, "candidate_source_files": source_evidence,
        "baseline": {"version_code": 45, "version_name": "0.13.7-preview", "bytes": old_bytes, "sha256": old_sha,
            "retained_root": prior["root"], "retained_build_run_id": prior["build_run_id"],
            "retained_build_run_attempt": prior["build_run_attempt"], "source_backup_commit": base,
            "source_sha256": base_source, "publication_receipt_sha256": digest(publication_raw),
            "published_at": previous["published_at"]},
        "original_portfolio_cases_required": 14, "additional_color_frames_required": 52,
        "additional_lifecycle_cases_required": 4, "full_ui_stage_count": 15,
        "diagnostic_only": True, "release_gate_pass": False, "full_ui_suite_executed": False,
        "publication_authorized": False, "phone_verified": False,
        "administrative_timeout_changes": {"worker_seconds": {"before": 2700, "after": WORKER_SECONDS},
            "profile_step_minutes": {"before": None, "after": STEP_MINUTES},
            "job_minutes": {"before": 100, "after": JOB_MINUTES}, "canonical_lease_wait_seconds": 1200,
            "original_per_action_timeouts_changed": False},
    }
    return files, source_evidence, provenance, report_raw, export_raw, controller_raw


HOOK = r'''"""Actual original14 first, then52 color frames and4 lifecycle cases; full15 stays pending."""
import hashlib,json,os,re,stat,sys,xml.etree.ElementTree as ET
from pathlib import Path
import profile_ui_probe as module
from portfolio_ui_probe import exercise_portfolio
from profile_snapshot import restore_device_settings
from theme_state_evidence import _identity,exercise_theme_states
from theme_lifecycle_probe import exercise_theme_lifecycle,strict_night_setting

ADMITTED = {}
SENTINEL = 'Diagnostic only: full UI suite was deliberately not claimed'
PORTFOLIO = ('discovery/ready','dossier/ready','history/ready','history/partial','quotes/ready','markets/ready','appearance/ready')

def require(value,message):
    if not value:raise AssertionError(message)

def receipt(folder,name,value):
    path=folder/name
    meta=path.lstat()
    require(stat.S_ISREG(meta.st_mode) and meta.st_nlink==1 and not path.is_symlink()
            and not getattr(meta,'st_file_attributes',0)&0x400 and 0<meta.st_size<8*1024**2,
            'Missing or unowned native receipt: '+name)
    raw=path.read_bytes()
    require(json.loads(raw)==json.loads(json.dumps(value,allow_nan=False)),
            'Returned native result differs from its persisted receipt: '+name)
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def focused(device,read_tree):
    probe=module.ProfileProbe(device);probe.read_tree=read_tree
    root=Path(module.__file__).resolve().parents[2]
    folder=root/'app/build/outputs/apk/preview/ui-screens'
    require(not folder.is_symlink() and folder.resolve().is_relative_to(root),'Focused output directory escapes the owned source')
    report={'diagnostic_only':True,'release_gate_pass':False,'portfolio_cases_complete':False,
            'colors_complete':False,'lifecycle_complete':False,'focused_complete':False,
            'full15_executed':False,'full15_accepted':False,'evidence':{},'device_settings_restored':False}
    original_night=original_scale=None
    failure=None;traceback=None
    try:
        admission=_identity(probe,ADMITTED)
        require(admission['api']==37 and admission['page_size_bytes']==16384,'Wrong actual native46 kernel')
        report['native_admission']=admission
        original_night=strict_night_setting(probe.command('shell','cmd','uimode','night'))
        require(original_night in {'yes','no'},'Finite lifecycle gate requires an existing explicit global yes/no policy')
        original_scale=probe.command('shell','settings','get','system','font_scale').strip()
        require(re.fullmatch(r'[0-9](?:\.[0-9]{1,3})?',original_scale) and .5<=float(original_scale)<=3,
                'Original native46 font scale cannot be restored')
        report['portfolio']=exercise_portfolio(probe)
        actual=[(row['case'],row['font_scale']) for row in report['portfolio']['cases']]
        require(actual==[(name,scale) for scale in (1.0,2.0) for name in PORTFOLIO]
                and all(row['checks'] and len(row['checks'])==len(set(row['checks'])) for row in report['portfolio']['cases'])
                and report['portfolio']['actual_device_observations'] is True
                and report['portfolio']['production_destination_screens_exercised'] is True
                and report['portfolio']['real_broker_or_model_called'] is False,
                'All unchanged original fourteen real portfolio cases are required before extra themes')
        report['evidence']['portfolio-verification.json']=receipt(folder,'portfolio-verification.json',report['portfolio'])
        report['portfolio_cases_complete']=True
        colors=exercise_theme_states(probe,ADMITTED)
        require(colors['status']=='passed' and colors['capture_count']==colors['expected_capture_count']==52
                and len(colors['captures'])==52 and colors['restoration']['restored'] is True
                and colors['original15_changed'] is False and colors['full_acceptance_claimed'] is False
                and all(colors['identity'][key]==value for key,value in ADMITTED.items()),
                'Additional actual52-frame color evidence is incomplete')
        report['evidence']['theme-state-evidence.json']=receipt(folder,'theme-state-evidence.json',colors)
        report['colors_complete']=True
        report['lifecycle_admission']=_identity(probe,ADMITTED)
        lifecycle=exercise_theme_lifecycle(probe)
        require(lifecycle['status']=='passed' and lifecycle['restoration']['restored'] is True
                and lifecycle['fixture_apk_sha256']==ADMITTED['debug_apk_sha256']
                and lifecycle['actual_device_observations'] is True and lifecycle['full_release_gate_claimed'] is False
                and len(lifecycle['cases'])==4
                and {(row['forced_mode'],row['font_scale']) for row in lifecycle['cases']}==
                    {(mode,scale) for mode in ('LIGHT','DARK') for scale in (1.0,2.0)}
                and all(row['status']=='passed' for row in lifecycle['cases']),
                'Additional actual four lifecycle cases are incomplete')
        report['evidence']['theme-lifecycle-verification.json']=receipt(folder,'theme-lifecycle-verification.json',lifecycle)
        report['lifecycle_complete']=True
    except BaseException as error:
        failure,traceback=error,error.__traceback__
        if report.get('native_admission'):
            try:
                folder.mkdir(parents=True,exist_ok=True)
                # Preserve the old original14 failure capture; additional theme
                # failures add XML only, never a fifty-third color capture.
                if not report['portfolio_cases_complete']:probe.capture('portfolio-focused-failure')
                path=folder/'theme46-focused-failure.xml'
                require(not path.is_symlink(),'Diagnostic XML is a link')
                path.write_bytes(ET.tostring(probe.tree(),encoding='utf-8',xml_declaration=True))
            except Exception as capture_error:report['failure_capture_error']=type(capture_error).__name__
    finally:
        if original_scale is not None and original_night is not None:
            try:
                restore_device_settings(probe.command,original_scale,original_night)
                require(probe.command('shell','settings','get','system','font_scale').strip()==original_scale
                        and strict_night_setting(probe.command('shell','cmd','uimode','night'))==original_night,
                        'Native46 outer device settings did not restore exactly')
                report['device_settings_restored']=True
            except BaseException as error:
                report['device_settings_restore_error']=type(error).__name__+': '+str(error)
                if failure is None:failure,traceback=error,error.__traceback__
                else:failure.add_note('Outer device settings restoration failed: '+type(error).__name__+': '+str(error))
        complete=all(report[key] is True for key in ('portfolio_cases_complete','colors_complete',
                                                     'lifecycle_complete','device_settings_restored'))
        report['focused_complete']=complete and failure is None
        if report['focused_complete']:
            failure=AssertionError(SENTINEL)
            traceback=None
        require(failure is not None,'A focused diagnostic cannot return as a complete release gate')
        report.update(error_type=type(failure).__name__,error=str(failure)[:1000])
        folder.mkdir(parents=True,exist_ok=True)
        path=folder/'portfolio-theme-focused-observations.json'
        require(not folder.is_symlink() and not path.is_symlink(),'Focused evidence path is a link')
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('NATIVE46_FOCUSED_OBSERVATIONS='+json.dumps({key:report[key] for key in
            ('portfolio_cases_complete','colors_complete','lifecycle_complete','focused_complete',
             'device_settings_restored','full15_accepted','error_type','error')}),flush=True)
    raise failure.with_traceback(traceback)

module.exercise_checks=focused
'''


SUMMARY_SCRIPT = r'''const fs=require('node:fs'),p=require('node:path'),crypto=require('node:crypto');
const folder=p.join(process.env.SOURCE_ROOT,'app/build/outputs/apk/preview/ui-screens');
function read(name) {
  const path=p.join(folder,name);
  if(!fs.existsSync(path)) return null;
  const s=fs.lstatSync(path);
  if(!s.isFile()||s.isSymbolicLink()||s.nlink!==1||s.size<=0||s.size>8*1024*1024) throw new Error('Unowned native receipt');
  const bytes=fs.readFileSync(path);
  return {value:JSON.parse(bytes.toString('utf8')),bytes:bytes.length,sha256:crypto.createHash('sha256').update(bytes).digest('hex')};
}
const observed=read('portfolio-theme-focused-observations.json');
const source=observed?observed.value:{};
function bound(name) {
  const actual=read(name), expected=source.evidence&&source.evidence[name];
  return actual&&expected&&actual.bytes===expected.bytes&&actual.sha256===expected.sha256?actual:null;
}
const portfolio=bound('portfolio-verification.json'),colors=bound('theme-state-evidence.json'),life=bound('theme-lifecycle-verification.json');
const originalNames=['discovery/ready','dossier/ready','history/ready','history/partial','quotes/ready','markets/ready','appearance/ready'];
const expectedPortfolio=[1,2].flatMap(scale=>originalNames.map(name=>name+'@'+scale));
const originalCases=portfolio&&Array.isArray(portfolio.value.cases)?portfolio.value.cases:[];
const originalComplete=source.portfolio_cases_complete===true&&portfolio&&originalCases.length===14
  &&JSON.stringify(originalCases.map(row=>row.case+'@'+row.font_scale))===JSON.stringify(expectedPortfolio)
  &&originalCases.every(row=>Array.isArray(row.checks)&&row.checks.length>0&&new Set(row.checks).size===row.checks.length)
  &&portfolio.value.actual_device_observations===true&&portfolio.value.production_destination_screens_exercised===true
  &&portfolio.value.real_broker_or_model_called===false;
function admitted(value) { return value&&Object.entries(identity.admitted).every(([key,v])=>value[key]===v)
  &&value.installed_debug_apk_sha256===identity.admitted.debug_apk_sha256
  &&value.installed_driver_apk_sha256===identity.admitted.driver_apk_sha256&&value.api===37&&value.page_size_bytes===16384; }
const expectedColor=[];
for(const mode of ['LIGHT','DARK']) for(const accent of ['AURORA','OCEAN','IRIS']) for(const scale of [1,2])
  for(const group of ['actions','fields','canvas','overlay']) expectedColor.push([mode,accent,scale,group].join('|'));
for(const mode of ['LIGHT','DARK']) for(const scale of [1,2]) expectedColor.push([mode,'AURORA',scale,'calendar'].join('|'));
const frames=colors&&Array.isArray(colors.value.captures)?colors.value.captures:[];
const actualColor=frames.map(row=>[row.observation.mode,row.observation.accent,row.observation.font_scale,row.observation.group].join('|'));
const colorsComplete=source.colors_complete===true&&colors&&colors.value.status==='passed'
  &&colors.value.capture_count===52&&colors.value.expected_capture_count===52&&frames.length===52
  &&new Set(actualColor).size===52&&expectedColor.every(key=>actualColor.includes(key))
  &&colors.value.restoration.restored===true&&colors.value.original15_changed===false&&colors.value.full_acceptance_claimed===false
  &&admitted(colors.value.identity);
const cases=life&&Array.isArray(life.value.cases)?life.value.cases:[];
const lifeKeys=cases.map(row=>row.forced_mode+'|'+row.font_scale);
const lifecycleComplete=source.lifecycle_complete===true&&life&&life.value.status==='passed'
  &&life.value.restoration.restored===true&&life.value.fixture_apk_sha256===identity.admitted.debug_apk_sha256
  &&life.value.actual_device_observations===true&&life.value.full_release_gate_claimed===false
  &&cases.length===4&&new Set(lifeKeys).size===4&&['LIGHT|1','LIGHT|2','DARK|1','DARK|2'].every(key=>lifeKeys.includes(key))
  &&cases.every(row=>row.status==='passed')&&admitted(source.lifecycle_admission);
const complete=Boolean(originalComplete&&colorsComplete&&lifecycleComplete&&admitted(source.native_admission)
  &&source.diagnostic_only===true&&source.release_gate_pass===false&&source.full15_executed===false&&source.full15_accepted===false
  &&source.device_settings_restored===true&&source.focused_complete===true&&source.error_type==='AssertionError'
  &&source.error==='Diagnostic only: full UI suite was deliberately not claimed');
function proof(value) {return value?{bytes:value.bytes,sha256:value.sha256}:null;}
const report={...identity,diagnostic_only:true,release_gate_pass:false,
  original14:{complete:Boolean(originalComplete),required_cases:14,observed_cases:originalCases.length,receipt:proof(portfolio)},
  themes:{complete,colors:{complete:Boolean(colorsComplete),required_frames:52,observed_frames:frames.length,receipt:proof(colors)},
    lifecycle:{complete:Boolean(lifecycleComplete),required_cases:4,observed_cases:cases.length,receipt:proof(life)}},
  full15:{executed:false,accepted:false,required_stages:15},focused_observations:proof(observed),
  actual_outer_restoration:source.device_settings_restored===true,error_type:source.error_type||'missing',error:source.error||'focused_report_missing'};
const state=p.join(process.env.RUNNER_TEMP,'n00-native46-focused-'+process.env.GITHUB_RUN_ID+'-'+process.env.GITHUB_RUN_ATTEMPT);
fs.writeFileSync(p.join(state,'native46-original14-summary.json'),JSON.stringify(report,null,2)+'\n');
core.setOutput('original14_complete',String(Boolean(originalComplete)));core.setOutput('themes_complete',String(complete));
core.info('N00_ORIGINAL14_COMPLETE='+String(Boolean(originalComplete)));core.info('N00_THEME46_COMPLETE='+String(complete));core.info('N00_FULL15_ACCEPTED=false');
const title=complete?'Original14 and finite theme observations completed; full matrix remains pending':'Focused observations incomplete; full matrix remains pending';
const fence=String.fromCharCode(96).repeat(3);
await github.rest.checks.create({...context.repo,name:'N00 candidate46 original14 and themes (diagnostic only)',
  head_sha:context.sha,status:'completed',conclusion:'neutral',output:{title,summary:fence+'json\n'+JSON.stringify(report,null,2)+'\n'+fence}});
'''


def render(files, source_evidence, provenance, report_raw, export_raw, controller_raw):
    native45 = administrative("prepare_native45_counter.py")
    helper = native45.helpers()
    original = pinned("native44-bound/n00-runtime.py").decode()
    pinned("native43/n00-portfolio-focused-hook.py")
    admitted = {"source_inventory_sha256": provenance["source_sha256"],
                "debug_apk_sha256": files[APK_PATHS[1]][1], "driver_apk_sha256": files[APK_PATHS[2]][1],
                "version_code": 46, "version_name": "0.13.8-debug"}
    hook = helper.assignment(HOOK, "ADMITTED", admitted)
    runtime = original
    for name, value in (("BASE_COMMIT", provenance["source_backup_commit"]), ("SOURCE_HASH", provenance["source_sha256"]),
                        ("SOURCE_EVIDENCE", source_evidence), ("BUILD_PROVENANCE", provenance), ("FILES", files)):
        runtime = helper.assignment(runtime, name, value)
    previous = provenance["baseline"]
    runtime = helper.replace_once(runtime,
        "PREVIOUS_HASH='4e9bf0a2fd54d8ab4b9d49ef9ddf96bc14a274ac4c145585fcfdb88d6ae774b6'",
        "PREVIOUS_HASH=" + repr(previous["sha256"]))
    baseline = next(line for line in runtime.splitlines() if line.startswith("BASELINE = "))
    runtime = helper.replace_once(runtime, baseline, "BASELINE = pathlib.Path(" +
        repr(str(PureWindowsPath(previous["retained_root"]) / PureWindowsPath(APK_PATHS[0]))) + ")")
    need(runtime.count("st_size==29771254") == 2, "Pinned baseline-size guards changed")
    runtime = runtime.replace("st_size==29771254", "st_size==" + str(previous["bytes"]))
    replacements = (("n00-native44-focused-", "n00-native46-focused-"),
        ("native44-build-provenance.json", "native46-build-provenance.json"),
        ("native44-evidence-envelope.json", "native46-evidence-envelope.json"),
        ("n00_candidate44_portfolio_focused", "n00_candidate46_portfolio_and_themes_focused"),
        ("previous43.apk", "previous45.apk"), ("published_baseline43_changed", "published_baseline45_changed"),
        ("n00-portfolio-focused-hook.py", "n00-portfolio-theme-focused-hook.py"))
    for old, new in replacements:
        need(old in runtime, "Pinned runtime anchor missing: " + old)
        runtime = runtime.replace(old, new)
    runtime = helper.replace_once(runtime, "process.wait(timeout=2700)", f"process.wait(timeout={WORKER_SECONDS})")
    controller_check = """    controller=pathlib.Path(os.environ['RUNNER_TEMP'])/'n00-build-controller.json'
    regular(controller);need(sha(controller)==BUILD_PROVENANCE['build_controller_sha256'],'successful_build_controller_changed')
    lifecycle=json.loads(controller.read_text(encoding='utf-8'))
    need(lifecycle['worker_started'] is True and lifecycle['worker_exit_code']==0 and lifecycle['owned_processes_after']==0 and not lifecycle.get('error') and not lifecycle.get('cleanup_error'),'successful_build_cleanup_changed')
"""
    runtime = helper.replace_once(runtime, "    archive=json.loads(exported.read_text(encoding='utf-8'))\n",
        controller_check + "    archive=json.loads(exported.read_text(encoding='utf-8'))\n")
    anchor = "'original_portfolio_cases_required':14,'full_ui_stage_count':15"
    runtime = helper.replace_once(runtime, anchor,
        "'original_portfolio_cases_required':14,'additional_color_frames_required':52,'additional_lifecycle_cases_required':4,'full_ui_stage_count':15")
    old_nodes = {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(original).body
                 if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    new_nodes = {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(runtime).body
                 if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    need(set(old_nodes) == set(new_nodes), "Runtime ownership function set changed")
    for name in old_nodes.keys() - {"profile", "prepare", "export", "unchanged"}:
        need(old_nodes[name] == new_nodes[name], "OwnedJob/environment/source helper changed: " + name)
    # Reverse only the explicitly authorized administrative metadata and timeout
    # differences; no SDK/lease/process cleanup logic may move.
    for name in ("profile", "prepare", "unchanged", "export"):
        before = original.split("def " + name + "(", 1)[1].split("\ndef ", 1)[0]
        after = runtime.split("def " + name + "(", 1)[1].split("\ndef ", 1)[0]
        after = after.replace(controller_check, "")
        after = after.replace("'original_portfolio_cases_required':14,'additional_color_frames_required':52,'additional_lifecycle_cases_required':4,'full_ui_stage_count':15", anchor)
        after = after.replace(f"process.wait(timeout={WORKER_SECONDS})", "process.wait(timeout=2700)")
        after = after.replace("st_size==" + str(previous["bytes"]), "st_size==29771254")
        for old, new in reversed(replacements):
            after = after.replace(new, old)
        need(before == after, "Native process/lease/SDK logic changed: " + name)
    ast.parse(hook)
    original_workflow = yaml.safe_load(pinned("native44-bound/workflow.yml"))
    workflow = copy.deepcopy(original_workflow)
    workflow["name"] = "N00 candidate46 original14 and finite light-dark theme observations"
    workflow["on"]["push"]["paths"] = [TARGET]
    workflow["concurrency"]["group"] = "analyst-n00-candidate46-portfolio-and-themes-focused"
    need(workflow["concurrency"]["cancel-in-progress"] is False, "Cancellation policy changed")
    job = workflow["jobs"]["develop"]
    need(job["timeout-minutes"] == 100 and job["runs-on"] == ["self-hosted", "Windows", "X64", "omni-cio-ci"],
         "Pinned Windows host/budget changed")
    job["name"] = "Observe unchanged original14 then52 actual color frames and4 lifecycle cases"
    job["timeout-minutes"] = JOB_MINUTES
    job["outputs"]["themes_complete"] = "${{ steps.focused_report.outputs.themes_complete }}"
    steps, staged, profile_step = [], False, 0
    for step in job["steps"]:
        if step.get("name", "").startswith("Stage verified focused transport "):
            if not staged:
                added = [helper.stage("n00-runtime.py", runtime.encode()),
                    helper.stage("n00-portfolio-theme-focused-hook.py", hook.encode()),
                    helper.stage("n00-successful-build-report.json", report_raw),
                    helper.stage("n00-build-export-receipt.json", export_raw),
                    helper.stage("n00-build-controller.json", controller_raw)]
                added[-1]["id"] = "setup"
                steps.extend(added); staged = True
            continue
        if step.get("uses", "").startswith("actions/checkout@"):
            need(step["with"]["ref"] == "1cc05586b6874bfdd0cdb80131d178de9f95870c"
                 and step["with"]["persist-credentials"] is False, "Pinned checkout policy changed")
            step["with"]["ref"] = provenance["source_backup_commit"]
        if step.get("id") == "prepare":
            step["name"] = "Verify exact tested source46 and actually published baseline45"
        if step.get("name") == "Original portfolio cases at fonts100 and200 on Android37 16KB":
            need("timeout-minutes" not in step, "Pinned native profile step already has a new budget")
            step["name"] = "Original14 first, then52 colors and4 lifecycle cases on Android37 16KB"
            step["timeout-minutes"] = STEP_MINUTES
            profile_step += 1
        if step.get("id") == "focused_report":
            identity = {key: provenance[key] for key in ("source_sha256", "build_run_id", "build_run_attempt", "build_report_sha256")}
            identity.update(source_commit=provenance["source_backup_commit"], admitted=admitted)
            step["name"] = "Report original14 and finite theme evidence separately from the full matrix"
            step["with"]["script"] = "const identity=" + json.dumps(identity, separators=(",", ":")) + ";\n" + SUMMARY_SCRIPT
        if step.get("uses", "").startswith("actions/upload-artifact@"):
            step["name"] = "Retain actual focused original14 and theme diagnostic evidence"
            step["with"]["name"] = "n00-candidate46-original14-themes-native-16384"
            step["with"]["path"] = step["with"]["path"].replace("n00-native44-focused-", "n00-native46-focused-")
        need(not step.get("continue-on-error"), "Diagnostic failure must remain visible")
        steps.append(step)
    need(staged and profile_step == 1, "Required native profile/staging step missing or duplicated")
    job["steps"] = steps
    for name in ("preflight", "collect", "cleanup", "result"):
        need(workflow["jobs"][name] == original_workflow["jobs"][name], "Private9417611 transfer/result policy changed")
    return {"n00-runtime.py": runtime.encode(), "n00-portfolio-theme-focused-hook.py": hook.encode(),
            "n00-successful-build-report.json": report_raw, "n00-build-export-receipt.json": export_raw,
            "n00-build-controller.json": controller_raw, "build-provenance.json": encoded(provenance),
            "workflow.yml": yaml.safe_dump(workflow, allow_unicode=True, sort_keys=False, width=120).encode()}


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
         and destination.parent.resolve(strict=True) == destination.parent, "New canonical output directory required")
    values = validate(request)
    outputs = render(*values)
    receipt = {"schema": 1, "state": "prepared_only_no_execution", "target_workflow": TARGET,
        "request_sha256": digest(raw), "source_backup_commit": request["source_backup_commit"],
        "source_sha256": request["source_sha256"], "original14_executed": False, "color_frames_executed": 0,
        "lifecycle_cases_executed": 0, "full15_accepted": False, "application_or_test_execution": False,
        "publication_performed": False, "phone_verified": False,
        "administrative_timeout_changes": values[2]["administrative_timeout_changes"],
        "files": {name: {"bytes": len(data), "sha256": digest(data)} for name, data in outputs.items()}}
    outputs["preparation.json"] = encoded(receipt)
    destination.mkdir()
    for name, data in outputs.items():
        with (destination / name).open("xb") as stream:
            stream.write(data)
    print(json.dumps({key: value for key, value in receipt.items() if key != "files"}))


if __name__ == "__main__":
    main()
