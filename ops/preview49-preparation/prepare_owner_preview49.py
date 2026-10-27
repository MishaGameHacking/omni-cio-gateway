"""Prepare preview49 publication from exact Windows/build and deployment receipts.

Administrative generation only. No application, tests, servers or devices run
here. Owner authorized an intermediate build; native acceptance is explicitly unclaimed.
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
TARGET = ".github/workflows/deliver-preview49.yml"
PACKAGE = "ru.omnicio.app.debug"
CERT = "bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1"
PREVIOUS_SHA = "85fb8b3c3e0020080a421efaae1c101df0e55f97bacb791064e1b1cbaa4a8df1"
PREVIOUS_BYTES = 29937843
APK = "app/build/outputs/apk/preview/app-preview.apk"
DEBUG = "app/build/outputs/apk/debug/app-debug.apk"
TEMPLATES = {
    "publish-preview44.py": "26b89e1a71d52d28f6e754dd9f7d5d12a6296a9043f0c6b9cfe7f3f945d1a661",
    "verify-public44.py": "5b43563f3ef8396a00c570c5dedac6e668844f55d4e0ceb3122e3ec494b5baf0",
    "hosted-delivery.py": "9bdfd8e0510a4aee2bd54b6d904f26fb2ed879e9ce63dd2b0c5704e6e34f1420",
    "workflow.yml": "cd457ae8dc968250efae6c9e40d3b5355437671882cc183eedb79ce731e52a70",
}


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
    helper = load_admin('administrative_delivery44', 'prep/delivery44/prepare_delivery44.py',
        '64db4d35e4fa983ac0d90f0398a9edbfed6263851fe03f1460c9671828ff8ab4')
    verifier = load_admin('administrative_calendar49_build', 'calendar49-runtime-deployment/prepare-deployment.py',
        '87e095e25fb6219246d609bc0668ab9974671a855e949c73cda17b13babf0b9e')
    return helper, verifier


def validate(helper, verifier, request):
    need(set(request) == {'schema', 'build_request', 'baseline_publication', 'runtime_verification',
        'owner_requested_intermediate_without_full_native'} and request['schema'] == 1 and
        request['owner_requested_intermediate_without_full_native'] is True, 'explicit_intermediate49_request_required')
    build_request, _ = helper.evidence(request, 'build_request')
    expected, _ = verifier.validate(helper, build_request)
    report, report_raw = helper.evidence(build_request, 'build_report')
    exported, export_raw = helper.evidence(build_request, 'build_export_receipt')
    baseline, baseline_raw = helper.evidence(request, 'baseline_publication')
    published = baseline['publication']
    need(baseline['https_policy_verified'] is True and baseline['https_entire_apk_download_verified'] is True and
        baseline['backend_health_http'] == 200 and published['version_code'] == published['channel_version'] == 48 and
        published['version_name'] == '0.14.1-preview' and published['package_name'] == PACKAGE and
        baseline['https_apk_bytes'] == published['apk_bytes'] == PREVIOUS_BYTES and
        baseline['https_apk_sha256'] == published['apk_sha256'] == PREVIOUS_SHA and
        published['certificate_sha256'] == CERT and published['windows_run_id'] == 40400521138 and
        published['source_sha256'] == '26d1ccf6b9685925291edb968f17ef091b145831d7c6ca791e5e942246af49fa',
        'actual_published48_baseline_required')
    verification, verification_raw = helper.evidence(request, 'runtime_verification')
    deployed = verification['deployment']
    need(verification['kind'] == 'calendar49_public_verification' and
        verification['server9417611_verified_by_pinned_transport'] is True and
        deployed['kind'] == 'calendar49_exact_nine_file_deployment' and
        deployed['status'] in {'deployed_verified', 'already_deployed_verified'} and
        deployed['runtime_server_id'] == 9417611 and deployed['source_sha256'] == expected['source_sha256'] and
        deployed['source_backup_commit'] == expected['source_backup_commit'] and deployed['archive'] == expected['archive'] and
        deployed['build_report'] == expected['build_report'] and
        deployed['runtime_sources'] == {name: row['new'] for name, row in expected['runtime_sources'].items()} and
        deployed['full_windows_check_and_build_passed'] is True and
        deployed['actual_calendar_test_evidence']['original_calendar_test_count'] == expected['calendar_test_count'] and
        verification['independent_public']['health_http'] == 200 and
        verification['independent_public']['update_version_code'] == 48 and
        verification['github_build'] == {'run_id': expected['github']['run_id'],
            'run_attempt': expected['github']['run_attempt'], 'workflow_sha': expected['github']['workflow_sha'],
            'successful_jobs': 5, 'current_attempt_verified': True}, 'tested_calendar49_must_be_deployed_before_its_apk')
    for name in (APK, DEBUG, 'ci-ui-driver/build/outputs/apk/debug/ci-ui-driver-debug.apk'):
        item = report['apks'][name]
        need(set(item) == {'bytes', 'sha256'}, 'invalid_actual_apk_identity')
        helper.positive(item['bytes'], 128 * 1024**2)
        helper.digest(item['sha256'])
    need(report['build']['apk_sha256'] == report['apks'][APK]['sha256'] != PREVIOUS_SHA, 'new49_apk_required')
    native = {'status': 'not_executed_for_published_build', 'run_id': None,
              'full_runtime_matrix_passed': False, 'physical_phone_verified': False}
    return {'request': build_request, 'build': report, 'export': exported, 'native': native,
        'build_report_sha256': sha(report_raw), 'build_export_receipt_sha256': sha(export_raw),
        'baseline_publication_sha256': sha(baseline_raw), 'runtime_deployment': deployed,
        'runtime_verification_sha256': sha(verification_raw)}


def authorization(binding):
    build, exported = binding['build'], binding['export']
    return {'kind': 'owner_requested_latest_built_preview_delivery',
        'owner_request': 'Вся работа на ноуте; обновить рабочее приложение и APK на Timeweb без повторной полной матрицы',
        'explicit_intermediate_preview': True, 'date': build['finished_at'][:10],
        'package_name': PACKAGE, 'version_code': 49,
        'apk_sha256': build['apks'][APK]['sha256'], 'apk_bytes': build['apks'][APK]['bytes'],
        'certificate_sha256': CERT, 'source_archive_sha256': exported['sha256'], 'source_archive_bytes': exported['bytes'],
        'source_sha256': binding['request']['source_sha256'], 'source_backup_commit': binding['request']['source_backup_commit'],
        'build_report_sha256': binding['build_report_sha256'], 'build_export_receipt_sha256': binding['build_export_receipt_sha256'],
        'windows_run_id': build['github']['run_id'], 'windows_run_attempt': build['github']['run_attempt'],
        'full_check_and_build_passed': True, 'preview_install_smoke': binding['native'],
        'native_status': 'not_executed_for_published_build', 'full15_runtime_matrix_passed': False,
        'complete_release_gate_passed': False, 'runtime_pass': False, 'phone_verified': False,
        'baseline_publication_sha256': binding['baseline_publication_sha256'],
        'calendar_runtime_verification_sha256': binding['runtime_verification_sha256'],
        'calendar_runtime_sources': binding['runtime_deployment']['runtime_sources'],
        'prior_native_attempt': {'run_id': 40389869187, 'build_run_id': 40386457173, 'status': 'failed',
            'artifact_id': 12685050936,
            'artifact_sha256': '9f8dc6419f23bcaf4fd964684582dcf7920fae9a0394aba44555cdd7c7869762',
            'is_evidence_for_published_build': False},
        'reason_for_current_manifest_change': 'Owner requests an intermediate working update; exact build, signature, prior channel and deployed mandate are verified. Native/phone acceptance remains open.',
        'database_mutations_performed': False, 'session_or_owner_binding_mutations_performed': False,
        'backend_deployment_performed': False, 'service_restart_performed': False,
        'signing_key_mutations_performed': False, 'trading_orders_submitted': False, 'paid_ai_calls_performed': False}


def literals(helper, text, binding, verifier=False):
    identities = {
        "f0af0b45515143f8abb2c28e73d0d484acde5c6a36e18de1b398692bc45a4cf6": binding["build"]["apks"][APK]["sha256"],
        "4e9bf0a2fd54d8ab4b9d49ef9ddf96bc14a274ac4c145585fcfdb88d6ae774b6": PREVIOUS_SHA,
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
            values = {44: 49, 43: 48}
            if verifier:
                values.update({29771254: binding["build"]["apks"][APK]["bytes"],
                               68927139: binding["export"]["bytes"]})
            value = values.get(value, value)
        elif type(value) is str:
            if verifier and value in identities:
                value = identities[value]
            else:
                for old, new in (("0.13.6-preview", "0.14.2-preview"), ("0.13.5-preview", "0.14.1-preview"),
                    ("upgrade43_to44", "upgrade48_to49"), ("upgrade44_bootstrap", "upgrade49_bootstrap"),
                    ("previous43", "previous48"), ("candidate44", "candidate49"),
                    ("preview44", "preview49"), ("PREVIEW44", "PREVIEW49"),
                    ("exact44", "exact49"), ("Analyst-AI-44-", "Analyst-AI-49-")):
                    value = value.replace(old, new)
        if value != node.value:
            replacements.append((node, repr(value)))
    return helper.edits(text, replacements)




def render(helper, binding, request_sha):
    templates = {name: helper.checked_bytes(REFERENCE / name, expected).decode() for name, expected in TEMPLATES.items()}
    build, exported = binding["build"], binding["export"]
    run, attempt = build["github"]["run_id"], build["github"]["run_attempt"]
    text = literals(helper, templates["publish-preview44.py"], binding)
    for old, new in (("previous_is_exact43", "previous_is_exact48"), ("current_is_exact44", "current_is_exact49"),
                     ("exact44_reported_by_active_session=", "exact49_reported_by_active_session=")):
        need(old in text, "Publisher identifier changed")
        text = text.replace(old, new)
    for name, value in {"APK_SHA": build["apks"][APK]["sha256"], "APK_BYTES": build["apks"][APK]["bytes"],
        "OLD_SHA": PREVIOUS_SHA, "OLD_BYTES": PREVIOUS_BYTES, "ARCHIVE_SHA": exported["sha256"], "ARCHIVE_BYTES": exported["bytes"],
        "SOURCE_SHA": binding["request"]["source_sha256"], "SOURCE_BACKUP": binding["request"]["source_backup_commit"],
        "BUILD_REPORT_SHA": binding["build_report_sha256"]}.items():
        text = helper.assign(text, name, repr(value))
    text = helper.assign(text, "FOLDER", "pathlib.Path(" + repr(f"/var/lib/analyst-ai-build/incoming/windows-development-{run}-{attempt}") + ")")
    old_guard = "need(build['github']['run_id'] == 40282775349 and build['github']['run_attempt'] == 1, 'wrong_build_run')"
    need(text.count(old_guard) == 1, "Exact previous build guard changed")
    text = text.replace(old_guard, f"need(build['github']['run_id'] == {run} and build['github']['run_attempt'] == {attempt}, 'wrong_build_run')")
    text = helper.assign(text, "notes", repr("Тестовая версия 0.14.2-preview. Расписание брокера управляет фоновым опросом цен; события, новости и выплаты проверяются отдельно. Возобновление прерванного сбора, приоритеты задач и защита сохранённых данных. Торговля выключена; нативная приёмка остаётся открытой."))
    text = helper.assign(text, "authorization", pprint.pformat(authorization(binding), sort_dicts=False, width=110))
    guard = "\n# Bind this APK publication to the already deployed exact mandate sources.\n"
    guard += "required_runtime = " + repr(binding['runtime_deployment']['runtime_sources']) + "\n"
    guard += "for directory in (pathlib.Path('/opt'), pathlib.Path('/opt/analyst-ai'), pathlib.Path('/opt/analyst-ai/backend')):\n    trusted(directory, directory=True)\n"
    guard += "for name, item in required_runtime.items():\n    need(file_sha(pathlib.Path('/opt/analyst-ai/backend') / name, item['bytes']) == item['sha256'], 'calendar_runtime_source_changed_before_publication')\n"
    marker = "need(os.geteuid() == 0, 'root_required')"
    need(text.count(marker) == 1, 'root publication boundary changed')
    text = text.replace(marker, marker + guard, 1)
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
    workflow["name"] = "Deliver exact preview49 at the owner request"
    workflow["on"]["push"]["paths"] = [TARGET]
    job["steps"][1]["name"] = "Publish verified preview49 calendar and event dispatch; verify policy entire APK and health"
    job["steps"][1]["run"] = "python3 - <<'PY'\n" + hosted + "\nPY\n"
    for key in ("name", "path"):
        job["steps"][2]["with"][key] = job["steps"][2]["with"][key].replace("preview44", "preview49")
    raw_workflow = yaml.safe_dump(workflow, allow_unicode=True, sort_keys=False, width=120).encode()
    need(yaml.safe_load(raw_workflow) == workflow, "YAML roundtrip changed workflow")
    outputs = {"publish-preview49.py": text.encode(), "verify-public49.py": verifier.encode(),
        "remote-wrapper.py": remote.encode(), "hosted-delivery.py": hosted.encode(), "workflow.yml": raw_workflow}
    outputs["preparation.json"] = encoded({"schema": 1, "preparation_only": True, "request_sha256": request_sha,
        "target_workflow": TARGET, "source_backup_commit": binding["request"]["source_backup_commit"],
        "source_sha256": binding["request"]["source_sha256"], "native_evidence": binding["native"],
        "candidate": {"version_code": 49, "version_name": "0.14.2-preview", **build["apks"][APK]},
        "prior_channel": {"version_code": 48, "version_name": "0.14.1-preview", "bytes": PREVIOUS_BYTES, "sha256": PREVIOUS_SHA},
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
