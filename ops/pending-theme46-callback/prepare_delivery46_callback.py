"""Prepare preview46 publication from completed, exact Windows/native receipts.

Administrative generation only. No application, tests, servers or devices run
here. Original14, 52 color frames and four lifecycle cases must complete;
full15 and the physical phone remain separate, unfinished acceptance gates.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import pprint
import stat
import zipfile

import yaml

WORKSPACE = Path(__file__).resolve().parents[3]
CONTEXT = WORKSPACE / "context"
REFERENCE = CONTEXT / "prep/delivery44/rendered"
TARGET = ".github/workflows/deliver-preview46.yml"
PACKAGE = "ru.omnicio.app.debug"
CERT = "bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1"
TEMPLATE_APK_SHA = "f0af0b45515143f8abb2c28e73d0d484acde5c6a36e18de1b398692bc45a4cf6"
TEMPLATE_APK_BYTES = 29771254
APK = "app/build/outputs/apk/preview/app-preview.apk"
DEBUG = "app/build/outputs/apk/debug/app-debug.apk"
TEMPLATES = {
    "publish-preview44.py": "26b89e1a71d52d28f6e754dd9f7d5d12a6296a9043f0c6b9cfe7f3f945d1a661",
    "verify-public44.py": "5b43563f3ef8396a00c570c5dedac6e668844f55d4e0ceb3122e3ec494b5baf0",
    "hosted-delivery.py": "9bdfd8e0510a4aee2bd54b6d904f26fb2ed879e9ce63dd2b0c5704e6e34f1420",
    "workflow.yml": "cd457ae8dc968250efae6c9e40d3b5355437671882cc183eedb79ce731e52a70",
}
REQUIRED = {"portfolio-verification.json": 14, "theme-state-evidence.json": 52,
            "theme-lifecycle-verification.json": 4}
FOCUSED = "portfolio-theme-focused-observations.json"
SENTINEL = "Diagnostic only: full UI suite was deliberately not claimed"


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def load_admin(name, relative, expected):
    path = CONTEXT / relative
    need(path.is_file() and path.resolve(strict=True) == path and path.stat().st_nlink == 1,
         "Administrative helper is not a canonical regular file")
    raw = path.read_bytes()
    need(sha(raw) == expected, "Administrative helper changed")
    ast.parse(raw)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def helpers():
    delivery = load_admin("administrative_delivery44", "prep/delivery44/prepare_delivery44.py",
        "64db4d35e4fa983ac0d90f0398a9edbfed6263851fe03f1460c9671828ff8ab4")
    native = load_admin("administrative_themes46", "prepare_native46_callback.py",
        "b242293f01804d55ac6c516e25185bb2585da3d17ab13560163348f6553805d9")
    return delivery, native


def native_receipt(helper, item, expected, build, native_request):
    need(type(item) is dict and set(item) == {
        "path", "sha256", "bytes", "artifact_id", "run_id", "run_attempt"}, "Unexpected artifact reference")
    run, attempt = helper.positive(item["run_id"]), helper.positive(item["run_attempt"], 99999)
    helper.positive(item["artifact_id"])
    path = helper.path_under_context(item["path"])
    helper.verify_archive_file(path, item["sha256"], item["bytes"])
    owner, root = f"n00-native46-focused-{run}-{attempt}", f"windows-development-{run}-{attempt}"
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        need(len(entries) <= 10000 and len(names) == len(set(names))
             and sum(entry.file_size for entry in entries) <= 512 * 1024**2,
             "Unexpected native46 artifact inventory")
        for entry in entries:
            relative = PurePosixPath(entry.filename)
            need(not relative.is_absolute() and ".." not in relative.parts
                 and relative.as_posix() == entry.filename.rstrip("/") and "\\" not in entry.filename
                 and ":" not in entry.filename and not entry.flag_bits & 1
                 and stat.S_IFMT(entry.external_attr >> 16) not in (stat.S_IFLNK, stat.S_IFBLK, stat.S_IFCHR),
                 "Unsafe native46 artifact entry")

        def read(name, scope):
            matches = [entry for entry in entries if entry.filename.endswith("/" + name)
                       and scope in PurePosixPath(entry.filename).parts]
            need(len(matches) == 1, "Missing or ambiguous evidence: " + name)
            entry = matches[0]
            need(not entry.is_dir() and 0 < entry.file_size <= 8 * 1024**2, "Invalid native evidence size")
            raw = archive.read(entry)
            need(len(raw) == entry.file_size, "Truncated native evidence")
            return helper.decoded(raw), raw

        provenance, provenance_raw = read("native46-build-provenance.json", owner)
        summary, summary_raw = read("native46-original14-summary.json", owner)
        envelope, envelope_raw = read("native46-evidence-envelope.json", owner)
        runtime, runtime_raw = read("runtime-16384.json", owner)
        installed, installed_raw = read("install-api37-16384/install-results.json", root)
        reports = {name: read("ui-screens/" + name, root) for name in (*REQUIRED, FOCUSED)}
    helper.verify_archive_file(path, item["sha256"], item["bytes"])
    need(provenance == expected, "Native46 provenance differs from the reviewed Windows build")
    need(envelope["kind"] == "n00_candidate46_portfolio_and_themes_focused"
         and envelope["build_provenance"] == expected
         and envelope["source_commit"] == native_request["source_backup_commit"]
         and envelope["base_source_sha256"] == envelope["source_sha256"] == native_request["source_sha256"]
         and envelope["input_files"] == expected["input_apks"]
         and envelope["test_patch_sha256"] is None
         and envelope["original_portfolio_cases_required"] == 14
         and envelope["additional_color_frames_required"] == 52
         and envelope["additional_lifecycle_cases_required"] == 4,
         "Native46 envelope identity or scope changed")
    for value in (provenance, summary, envelope):
        need(value["diagnostic_only"] is True and value["release_gate_pass"] is False,
             "Focused observations cannot claim full release acceptance")
    for value in (provenance, envelope):
        need(value["phone_verified"] is False and value["publication_authorized"] is False
             and value["full_ui_suite_executed"] is False and value["full_ui_stage_count"] == 15,
             "Native46 acceptance scope changed")
    for name, raw in {
        "controller/native46-build-provenance.json": provenance_raw,
        "controller/native46-original14-summary.json": summary_raw,
        "controller/runtime-16384.json": runtime_raw,
        "install-api37-16384/install-results.json": installed_raw,
        **{"ui-screens/" + name: raw for name, (_, raw) in reports.items()},
    }.items():
        need(envelope["files"][name] == {"bytes": len(raw), "sha256": sha(raw)},
             "Native46 evidence differs from its envelope: " + name)
    admitted = {"source_inventory_sha256": native_request["source_sha256"],
                "debug_apk_sha256": build["apks"][DEBUG]["sha256"],
                "driver_apk_sha256": expected["input_apks"]["ci-ui-driver/build/outputs/apk/debug/ci-ui-driver-debug.apk"][1],
                "version_code": 46, "version_name": "0.13.8-debug"}
    need(summary["source_commit"] == native_request["source_backup_commit"]
         and summary["source_sha256"] == native_request["source_sha256"]
         and summary["build_run_id"] == expected["build_run_id"]
         and summary["build_run_attempt"] == expected["build_run_attempt"]
         and summary["build_report_sha256"] == expected["build_report_sha256"]
         and summary["admitted"] == admitted, "Native46 summary identity differs")
    need(summary["full15"] == {"executed": False, "accepted": False, "required_stages": 15}
         and summary["themes"]["complete"] is True and summary["actual_outer_restoration"] is True
         and summary["error_type"] == "AssertionError" and summary["error"] == SENTINEL,
         "Focused native46 did not finish with its deliberate diagnostic boundary")
    observations, observed_raw = reports[FOCUSED]
    need(summary["focused_observations"] == {"bytes": len(observed_raw), "sha256": sha(observed_raw)}
         and observations["diagnostic_only"] is True and observations["release_gate_pass"] is False
         and observations["portfolio_cases_complete"] is True and observations["colors_complete"] is True
         and observations["lifecycle_complete"] is True and observations["focused_complete"] is True
         and observations["device_settings_restored"] is True and observations["full15_executed"] is False
         and observations["full15_accepted"] is False and observations["error_type"] == "AssertionError"
         and observations["error"] == SENTINEL, "Focused native46 observations are incomplete")

    def identity(value):
        need(all(type(value.get(k)) is type(v) and value[k] == v for k, v in admitted.items())
             and value["installed_debug_apk_sha256"] == admitted["debug_apk_sha256"]
             and value["installed_driver_apk_sha256"] == admitted["driver_apk_sha256"]
             and value["api"] == 37 and value["page_size_bytes"] == 16384,
             "Native46 installed debug/driver identity changed")

    identity(observations["native_admission"])
    identity(observations["lifecycle_admission"])
    for name in REQUIRED:
        _, raw = reports[name]
        need(observations["evidence"][name] == {"bytes": len(raw), "sha256": sha(raw)},
             "Focused native46 report has an unbound child receipt")
    portfolio, portfolio_raw = reports["portfolio-verification.json"]
    need(observations["portfolio"] == portfolio, "Focused original14 differs from its saved result")
    expected_cases = [(name, scale) for scale in (1.0, 2.0) for name in
        ("discovery/ready", "dossier/ready", "history/ready", "history/partial", "quotes/ready", "markets/ready", "appearance/ready")]
    need([(row["case"], row["font_scale"]) for row in portfolio["cases"]] == expected_cases
         and all(row["checks"] and len(row["checks"]) == len(set(row["checks"])) for row in portfolio["cases"])
         and portfolio["actual_device_observations"] is True
         and portfolio["production_destination_screens_exercised"] is True
         and portfolio["real_broker_or_model_called"] is False and portfolio["physical_device_verified"] is False,
         "Original fourteen actual production cases are incomplete")
    need(summary["original14"] == {"complete": True, "required_cases": 14, "observed_cases": 14,
        "receipt": {"bytes": len(portfolio_raw), "sha256": sha(portfolio_raw)}}, "Original14 summary changed")
    colors, colors_raw = reports["theme-state-evidence.json"]
    expected_frames = {(mode, accent, scale, group) for mode in ("LIGHT", "DARK")
        for accent in ("AURORA", "OCEAN", "IRIS") for scale in (1.0, 2.0)
        for group in ("actions", "fields", "canvas", "overlay")}
    expected_frames |= {(mode, "AURORA", scale, "calendar") for mode in ("LIGHT", "DARK") for scale in (1.0, 2.0)}
    frames = [(r["observation"]["mode"], r["observation"]["accent"], r["observation"]["font_scale"],
               r["observation"]["group"]) for r in colors["captures"]]
    need(colors["schema_version"] == 1 and colors["status"] == "passed"
         and colors["capture_count"] == colors["expected_capture_count"] == len(frames) == 52
         and len(set(frames)) == 52 and set(frames) == expected_frames
         and colors["restoration"]["restored"] is True and colors["original15_changed"] is False
         and colors["full_acceptance_claimed"] is False, "Actual52-frame color coverage is incomplete")
    identity(colors["identity"])
    need(summary["themes"]["colors"] == {"complete": True, "required_frames": 52, "observed_frames": 52,
        "receipt": {"bytes": len(colors_raw), "sha256": sha(colors_raw)}}, "Color summary changed")
    life, life_raw = reports["theme-lifecycle-verification.json"]
    life_keys = [(row["forced_mode"], row["font_scale"]) for row in life["cases"]]
    need(life["status"] == "passed" and life["restoration"]["restored"] is True
         and life["fixture_apk_sha256"] == admitted["debug_apk_sha256"]
         and life["actual_device_observations"] is True and life["full_release_gate_claimed"] is False
         and len(life_keys) == len(set(life_keys)) == 4
         and set(life_keys) == {(mode, scale) for mode in ("LIGHT", "DARK") for scale in (1.0, 2.0)}
         and all(row["status"] == "passed" for row in life["cases"]), "Actual four lifecycle cases are incomplete")
    need(summary["themes"]["lifecycle"] == {"complete": True, "required_cases": 4, "observed_cases": 4,
        "receipt": {"bytes": len(life_raw), "sha256": sha(life_raw)}}, "Lifecycle summary changed")
    need(runtime["test_source_sha256"] == native_request["source_sha256"]
         and runtime["apk_sha256"] == build["apks"][APK]["sha256"] and runtime["host"] == "LAPTOP-NPSGA016"
         and runtime["page_bytes"] == 16384 and runtime["test_patch_sha256"] is None
         and type(runtime["exit_code"]) is int and runtime["exit_code"] == 1 and runtime.get("finished_at"),
         "Diagnostic sentinel or native46 runtime identity changed")
    need(type(installed) is list and installed, "Missing installation receipt")
    stages = {row["test"]: row for row in installed}
    need(len(stages) == len(installed), "Repeated native installation stage")
    for name in ("kernel_page_size", "upgrade_to_candidate", "upgrade_bootstrap_launch",
                 "candidate_clean_install", "bootstrap_activity_launch"):
        need(stages[name]["success"] is True and stages[name]["apk_sha256"] == build["apks"][APK]["sha256"],
             "Candidate46 installation/launch failed")
    need(stages["kernel_page_size"]["android_api"] == 37 and stages["kernel_page_size"]["page_size_bytes"] == 16384
         and stages["kernel_page_size"]["abi"] == "x86_64", "Native profile was not measured API37/16KB")
    need(stages["previous_clean_install"]["success"] is True
         and stages["previous_clean_install"]["apk_sha256"] == expected["baseline"]["sha256"]
         and stages["debug_ui_fixture_install"]["success"] is True
         and stages["debug_ui_fixture_install"]["apk_sha256"] == admitted["debug_apk_sha256"]
         and stages["profile_ui"]["success"] is False, "Exact upgrade or diagnostic fixture identity changed")
    return {"run_id": run, "run_attempt": attempt, "artifact_id": item["artifact_id"],
        "artifact_sha256": item["sha256"], "artifact_bytes": item["bytes"],
        "installation_json_sha256": sha(installed_raw), "build_provenance_sha256": sha(provenance_raw),
        "summary_sha256": sha(summary_raw), "envelope_sha256": sha(envelope_raw),
        "runtime_sha256": sha(runtime_raw), "runtime_exit_code": 1,
        "focused_observations_sha256": sha(observed_raw), "original14_complete": True,
        "color_frames_complete": True, "color_frames_required": 52, "lifecycle_complete": True,
        "lifecycle_cases_required": 4, "device_settings_restored": True, "full15_executed": False}



def validate(helper, native_helper, request):
    need(type(request) is dict and set(request) == {"schema", "native_request", "native_artifact"}
         and request["schema"] == 1, "Unexpected delivery46 request schema")
    native_request, _ = helper.evidence(request, "native_request")
    _, _, provenance, build_raw, export_raw, _ = native_helper.validate(native_request)
    build, exported = helper.decoded(build_raw), helper.decoded(export_raw)
    native = native_receipt(helper, request["native_artifact"], provenance, build, native_request)
    return {"request": native_request, "build": build, "export": exported, "native": native,
            "baseline": provenance["baseline"], "build_report_sha256": sha(build_raw),
            "build_export_receipt_sha256": sha(export_raw)}



def literals(helper, text, binding, verifier=False):
    identities = {
        TEMPLATE_APK_SHA: binding["build"]["apks"][APK]["sha256"],
        "4e9bf0a2fd54d8ab4b9d49ef9ddf96bc14a274ac4c145585fcfdb88d6ae774b6": binding["baseline"]["sha256"],
        "e34b717fa408fbe377d910a372933c35a2ba1bdddf02263b6daa477df70f93b9": binding["request"]["source_sha256"],
        "1cc05586b6874bfdd0cdb80131d178de9f95870c": binding["request"]["source_backup_commit"],
        "808a43afb0585b3cf2cd9519d54c525f51be4d66fa239e3d9c4c4257d2eafd40": binding["build_report_sha256"],
        "f8dd107e1714fcc1a3aeed4afd25b6d9efa3dca878b7106191f3fd77e4fa1b89": binding["export"]["sha256"],
    }
    replacements = []
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, ast.Constant):
            continue
        value = node.value
        if type(value) is int:
            values = {44: 46, 43: 45}
            if verifier:
                values.update({TEMPLATE_APK_BYTES: binding["build"]["apks"][APK]["bytes"],
                               68927139: binding["export"]["bytes"]})
            value = values.get(value, value)
        elif type(value) is str:
            if verifier and value in identities:
                value = identities[value]
            else:
                for old, new in (("0.13.6-preview", "0.13.8-preview"), ("0.13.5-preview", "0.13.7-preview"),
                    ("upgrade43_to44", "upgrade45_to46"), ("upgrade44_bootstrap", "upgrade46_bootstrap"),
                    ("previous43", "previous45"), ("candidate44", "candidate46"),
                    ("preview44", "preview46"), ("PREVIEW44", "PREVIEW46"),
                    ("exact44", "exact46"), ("Analyst-AI-44-", "Analyst-AI-46-")):
                    value = value.replace(old, new)
        if value != node.value:
            replacements.append((node, repr(value)))
    return helper.edits(text, replacements)



def authorization(binding):
    build, exported, native = binding["build"], binding["export"], binding["native"]
    return {"kind": "owner_requested_latest_built_preview_delivery",
        "owner_request": "Не забывай обновлять приложение! Постоянно если есть актуальная сборка апк то обнови ту что на телефоне!",
        "date": build["finished_at"][:10], "package_name": PACKAGE, "version_code": 46,
        "apk_sha256": build["apks"][APK]["sha256"], "apk_bytes": build["apks"][APK]["bytes"],
        "certificate_sha256": CERT, "source_archive_sha256": exported["sha256"], "source_archive_bytes": exported["bytes"],
        "source_sha256": binding["request"]["source_sha256"], "source_backup_commit": binding["request"]["source_backup_commit"],
        "build_report_sha256": binding["build_report_sha256"], "build_export_receipt_sha256": binding["build_export_receipt_sha256"],
        "windows_run_id": build["github"]["run_id"], "windows_run_attempt": build["github"]["run_attempt"],
        "full_check_and_build_passed": True,
        "preview_install_smoke": {**native, "evidence_verified_at_workflow_preparation": True,
            "android_api": 37, "abi": "x86_64", "page_size_bytes": 16384,
            "previous45_clean_install": True, "upgrade45_to46": True, "upgrade46_bootstrap_launch": True,
            "candidate46_clean_install": True, "candidate46_bootstrap_launch": True,
            "physical_phone_verified": False, "full_runtime_matrix_passed": False},
        "original14_run_id": native["run_id"], "original14_status": "completed_diagnostic_only",
        "theme_color_frames": 52, "theme_lifecycle_cases": 4,
        "full15_runtime_matrix_passed": False, "complete_release_gate_passed": False,
        "runtime_pass": False, "phone_verified": False,
        "reason_for_current_manifest_change": "Publish the exact latest built preview under the existing mandatory client update channel, as directly requested by the owner.",
        "database_mutations_performed": False, "session_or_owner_binding_mutations_performed": False,
        "backend_deployment_performed": False, "service_restart_performed": False,
        "signing_key_mutations_performed": False, "trading_orders_submitted": False, "paid_ai_calls_performed": False}



def render(helper, binding, request_sha):
    templates = {name: helper.checked_bytes(REFERENCE / name, expected).decode() for name, expected in TEMPLATES.items()}
    build, exported = binding["build"], binding["export"]
    run, attempt = build["github"]["run_id"], build["github"]["run_attempt"]
    text = literals(helper, templates["publish-preview44.py"], binding)
    for old, new in (("previous_is_exact43", "previous_is_exact45"), ("current_is_exact44", "current_is_exact46"),
                     ("exact44_reported_by_active_session=", "exact46_reported_by_active_session=")):
        need(old in text, "Publisher identifier changed")
        text = text.replace(old, new)
    for name, value in {"APK_SHA": build["apks"][APK]["sha256"], "APK_BYTES": build["apks"][APK]["bytes"],
        "OLD_SHA": binding["baseline"]["sha256"], "OLD_BYTES": binding["baseline"]["bytes"], "ARCHIVE_SHA": exported["sha256"], "ARCHIVE_BYTES": exported["bytes"],
        "SOURCE_SHA": binding["request"]["source_sha256"], "SOURCE_BACKUP": binding["request"]["source_backup_commit"],
        "BUILD_REPORT_SHA": binding["build_report_sha256"]}.items():
        text = helper.assign(text, name, repr(value))
    text = helper.assign(text, "FOLDER", "pathlib.Path(" + repr(f"/var/lib/analyst-ai-build/incoming/windows-development-{run}-{attempt}") + ")")
    old_guard = "need(build['github']['run_id'] == 40282775349 and build['github']['run_attempt'] == 1, 'wrong_build_run')"
    need(text.count(old_guard) == 1, "Exact previous build guard changed")
    text = text.replace(old_guard, f"need(build['github']['run_id'] == {run} and build['github']['run_attempt'] == {attempt}, 'wrong_build_run')")
    text = helper.assign(text, "notes", repr("Тестовая версия 0.13.8-preview. Обновлены светлая и тёмная темы, цвета элементов и системное оформление. Проверены исходные сценарии портфеля и отдельные сценарии тем; полная приёмка продолжается."))
    text = helper.assign(text, "authorization", pprint.pformat(authorization(binding), sort_dicts=False, width=110))
    functions = [{node.name: ast.dump(node, include_attributes=False) for node in ast.parse(source).body
                  if isinstance(node, ast.FunctionDef)} for source in (templates["publish-preview44.py"], text)]
    need(set(functions[0]) == set(functions[1]) and all(functions[0][name] == functions[1][name]
         for name in functions[0] if name != "observed_clients"), "Publication file/owner guards changed")
    for required in ("with publication_lock(directory):", "_existing_current(channel, directory, candidate)",
        "_resume_prepared(channel, directory, candidate)", "_stage_candidate(channel, directory, candidate, apk)",
        "'?mode=ro&cache=private'", "'PRAGMA query_only=ON'"):
        need(required in text, "Publication/observation guard missing")
    verifier = templates["verify-public44.py"]
    matches = [node for node in ast.parse(verifier).body if isinstance(node, ast.Assert)
               and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Subscript)
               and isinstance(node.test.left.slice, ast.Constant) and node.test.left.slice.value == "preview_install_smoke"]
    need(len(matches) == 1, "Exact installation assertion changed")
    verifier = helper.edits(verifier, [(matches[0], "assert receipt['preview_install_smoke'] == None")])
    verifier = literals(helper, verifier, binding, verifier=True)
    need(verifier.count("assert receipt['preview_install_smoke'] == None") == 1, "Installation binding marker changed")
    verifier = verifier.replace("assert receipt['preview_install_smoke'] == None",
        "assert receipt['preview_install_smoke'] == " + repr(authorization(binding)["preview_install_smoke"]))
    old_hosted = templates["hosted-delivery.py"]
    assignment = [node for node in ast.parse(old_hosted).body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == "remote" for target in node.targets)]
    need(len(assignment) == 1, "Transport prefix changed")
    prefix = "".join(old_hosted.splitlines(keepends=True)[:assignment[0].lineno - 1])
    need(sha(prefix.encode()) == helper.PREFIX_SHA, "Pinned9417611 administrative prefix changed")
    remote = "import subprocess\nresult=subprocess.run(['/opt/analyst-ai/venv/bin/python','-c'," + repr(text) + \
        "],stdin=subprocess.DEVNULL,timeout=180)\nraise SystemExit(result.returncode)\n"
    hosted = prefix + "remote = " + repr(remote) + "\n" + verifier
    for source in (text, verifier, remote, hosted):
        ast.parse(source)
    original = yaml.safe_load(templates["workflow.yml"])
    workflow = copy.deepcopy(original)
    need(workflow["concurrency"] == {"group": "owner-preview-release-publication", "cancel-in-progress": False}
         and workflow["on"]["push"]["branches"] == ["codex/timeweb-owner-prepare-2026-10-23"], "Publication branch/concurrency changed")
    job = workflow["jobs"]["deliver"]
    need(job["runs-on"] == "ubuntu-24.04" and len(job["steps"]) == 3
         and job["steps"][0]["with"]["ref"] == helper.PIN and job["steps"][0]["with"]["persist-credentials"] is False,
         "Pinned administrative job changed")
    workflow["name"] = "Deliver exact preview46 at the owner request"
    workflow["on"]["push"]["paths"] = [TARGET]
    job["steps"][1]["name"] = "Publish verified preview46 themes and verify policy entire APK and health"
    job["steps"][1]["run"] = "python3 - <<'PY'\n" + hosted + "\nPY\n"
    for key in ("name", "path"):
        job["steps"][2]["with"][key] = job["steps"][2]["with"][key].replace("preview44", "preview46")
    raw_workflow = yaml.safe_dump(workflow, allow_unicode=True, sort_keys=False, width=120).encode()
    need(yaml.safe_load(raw_workflow) == workflow, "YAML roundtrip changed workflow")
    outputs = {"publish-preview46.py": text.encode(), "verify-public46.py": verifier.encode(),
        "remote-wrapper.py": remote.encode(), "hosted-delivery.py": hosted.encode(), "workflow.yml": raw_workflow}
    outputs["preparation.json"] = encoded({"schema": 1, "preparation_only": True, "request_sha256": request_sha,
        "target_workflow": TARGET, "source_backup_commit": binding["request"]["source_backup_commit"],
        "source_sha256": binding["request"]["source_sha256"], "native_evidence": binding["native"],
        "candidate": {"version_code": 46, "version_name": "0.13.8-preview", **build["apks"][APK]},
        "prior_channel": {"version_code": 45, "version_name": "0.13.7-preview", "bytes": binding["baseline"]["bytes"], "sha256": binding["baseline"]["sha256"]},
        "full15_runtime_matrix_passed": False, "complete_release_gate_passed": False, "physical_phone_verified": False,
        "application_or_test_execution_performed": False, "publication_performed": False,
        "files": {name: {"bytes": len(raw), "sha256": sha(raw)} for name, raw in outputs.items()}})
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    helper, native_helper = helpers()
    request_raw = helper.checked_bytes(helper.path_under_context(args.request), args.request_sha256)
    binding = validate(helper, native_helper, helper.decoded(request_raw))
    outputs = render(helper, binding, sha(request_raw))
    destination = helper.path_under_context(args.output)
    need(destination.is_relative_to(CONTEXT / "prep") and not destination.exists()
         and destination.parent.resolve(strict=True) == destination.parent, "New canonical preparation folder required")
    destination.mkdir()
    for name, raw in outputs.items():
        with (destination / name).open("xb") as stream:
            stream.write(raw)
    print(json.dumps({"prepared_only": str(destination), "workflow_sha256": sha(outputs["workflow.yml"]),
                      "application_or_test_execution_performed": False, "publication_performed": False}))


if __name__ == "__main__":
    main()
