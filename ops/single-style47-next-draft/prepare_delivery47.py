"""Prepare preview47 publication from completed, exact Windows/native receipts.

Administrative generation only. No application, tests, servers or devices run
here. The both native design/autosave profiles must pass; full15 acceptance remains separate.
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
TARGET = ".github/workflows/deliver-preview47.yml"
PACKAGE = "ru.omnicio.app.debug"
CERT = "bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1"
PREVIOUS_SHA = "488f95a0c1527ebf5a172c7af675769cb8ed81c116d9ec24175fc89adab1da0d"
PREVIOUS_BYTES = 29820407
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
    delivery = load_admin('administrative_delivery44', 'prep/delivery44/prepare_delivery44.py',
        '64db4d35e4fa983ac0d90f0398a9edbfed6263851fe03f1460c9671828ff8ab4')
    native = load_admin('administrative_native47', 'design47/prepare_native47.py',
        '64ab543552f25c51f7a31a7e548fa44cc641f682b993e7b48ef7d59958e97d46')
    return delivery, native


def native_receipt(helper, item, expected, build):
    need(type(item) is dict and set(item) == {
        'path', 'sha256', 'bytes', 'artifact_id', 'run_id', 'run_attempt'}, 'Unexpected native artifact reference')
    run = helper.positive(item['run_id'])
    attempt = helper.positive(item['run_attempt'], 99999)
    helper.positive(item['artifact_id'])
    path = helper.path_under_context(item['path'])
    helper.verify_archive_file(path, item['sha256'], item['bytes'])
    owner = f'n00-native47-focused-{run}-{attempt}'
    root = f'windows-development-{run}-{attempt}'
    evidence = {}
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        need(len(entries) <= 10000 and len(names) == len(set(names))
             and sum(entry.file_size for entry in entries) <= 512 * 1024**2, 'Unexpected native inventory')
        for entry in entries:
            relative = PurePosixPath(entry.filename)
            need(not relative.is_absolute() and '..' not in relative.parts and '\\' not in entry.filename
                 and ':' not in entry.filename and not entry.flag_bits & 1
                 and stat.S_IFMT(entry.external_attr >> 16) not in (stat.S_IFLNK, stat.S_IFBLK, stat.S_IFCHR),
                 'Unsafe native artifact member')

        def read(name, scope, limit=4 * 1024**2):
            matches = [entry for entry in entries if entry.filename.endswith('/' + name)
                       and scope in PurePosixPath(entry.filename).parts]
            need(len(matches) == 1, 'Missing or ambiguous native evidence: ' + name)
            entry = matches[0]
            need(not entry.is_dir() and 0 < entry.file_size <= limit, 'Invalid native evidence size')
            raw = archive.read(entry)
            need(len(raw) == entry.file_size, 'Truncated native evidence')
            return raw

        provenance_raw = read('native47-build-provenance.json', owner)
        summary_raw = read('native47-design-summary.json', owner)
        envelope_raw = read('native47-evidence-envelope.json', owner)
        provenance, summary, envelope = (helper.decoded(raw) for raw in (provenance_raw, summary_raw, envelope_raw))
        need(provenance == expected and envelope['build_provenance'] == expected,
             'Native evidence belongs to another reviewed build')
        need(envelope['kind'] == 'n00_candidate47_design_focused'
             and envelope['source_commit'] == expected['source_backup_commit']
             and envelope['base_source_sha256'] == envelope['source_sha256'] == expected['source_sha256']
             and envelope['candidate_source_evidence'] == expected['candidate_source_files']
             and envelope['input_files'] == expected['input_apks']
             and envelope['test_patch_sha256'] == expected['native_hook_sha256'], 'Native envelope identity changed')
        for value in (provenance, summary, envelope):
            need(value['diagnostic_only'] is True and value['release_gate_pass'] is False,
                 'Focused checks cannot claim full release acceptance')
        for value in (provenance, envelope):
            need(value['phone_verified'] is False and value['publication_authorized'] is False
                 and value['full_ui_suite_executed'] is False and value['full_ui_stage_count'] == 15,
                 'Native scope changed')
        for key in ('source_sha256', 'source_backup_commit', 'build_run_id', 'build_run_attempt',
                    'build_report_sha256', 'native_hook_sha256'):
            need(summary[key] == expected[key], 'Summary binding changed: ' + key)
        need(summary['schema'] == 1 and summary['design47_complete'] is True
             and summary['full15_executed'] is False and summary['physical_phone_verified'] is False
             and set(summary['pages']) == {'16384', '4096'}, 'Both actual native profiles are required')
        evidence['controller/native47-build-provenance.json'] = provenance_raw
        evidence['controller/native47-design-summary.json'] = summary_raw
        profiles = {}
        for page, folder in ((16384, 'ui-screens-api37-16384'), (4096, 'ui-screens')):
            runtime_raw = read(f'runtime-{page}.json', owner)
            installed_raw = read(f'install-api37-{page}/install-results.json', root)
            observations_raw = read(folder + '/design47-focused-observations.json', root)
            runtime, installed, report = (helper.decoded(raw) for raw in (runtime_raw, installed_raw, observations_raw))
            observation = summary['pages'][str(page)]
            need(observation == {'complete': True, 'bytes': len(observations_raw),
                'sha256': sha(observations_raw), 'observations': report}, 'Native summary differs from original report')
            need(runtime['test_source_sha256'] == expected['source_sha256']
                 and runtime['apk_sha256'] == build['apks'][APK]['sha256']
                 and runtime['host'] == 'LAPTOP-NPSGA016' and runtime['page_bytes'] == page
                 and runtime['test_patch_sha256'] == expected['native_hook_sha256']
                 and type(runtime['exit_code']) is int and runtime['exit_code'] == 1
                 and runtime.get('finished_at'), 'Unexpected native runtime identity or sentinel')
            need(type(installed) is list and installed, 'Missing installation receipts')
            stages = {row['test']: row for row in installed}
            need(len(stages) == len(installed), 'Repeated installation stage')
            for name in ('kernel_page_size', 'upgrade_to_candidate', 'upgrade_bootstrap_launch',
                         'candidate_clean_install', 'bootstrap_activity_launch'):
                need(stages[name]['success'] is True and stages[name]['apk_sha256'] == build['apks'][APK]['sha256'],
                     'Candidate installation or launch failed: ' + name)
            measured = stages['kernel_page_size']
            need(measured['android_api'] == 37 and measured['page_size_bytes'] == page
                 and measured['abi'] == 'x86_64', 'The emulator profile was not actually measured')
            need(stages['previous_clean_install']['success'] is True
                 and stages['previous_clean_install']['apk_sha256'] == PREVIOUS_SHA
                 and stages['debug_ui_fixture_install']['success'] is True
                 and stages['debug_ui_fixture_install']['apk_sha256'] == build['apks'][DEBUG]['sha256']
                 and stages['profile_ui']['success'] is False, 'Baseline, fixture or diagnostic boundary changed')
            need(report['schema_version'] == 1 and report['status'] == 'passed'
                 and report['fixture_apk_sha256'] == build['apks'][DEBUG]['sha256']
                 and report['actual_device_observations'] is True and report['diagnostic_only'] is True
                 and report['release_gate_pass'] is False and report['full15_executed'] is False
                 and report['physical_phone_verified'] is False and report['real_order_execution'] is False
                 and report['external_broker_model_calls'] is False, 'Incomplete or mis-scoped live observations')
            for group in ('cases', 'appearance_restart_cases', 'autosave_cases'):
                need(len(report[group]) == 2 and {c['font_scale'] for c in report[group]} == {1.0, 2.0},
                     'Both font profiles are required: ' + group)
            captures = []
            for case in report['cases']:
                need(len(case['icons']) == len({i['id'] for i in case['icons']}) == 21
                     and [d['page'] for d in case['destinations']] == expected['required_destination_pages']
                     and case['server_mutations'] == 0 and case['minimum_touch_dp'] == 48
                     and case['before']['preferences'] == case['after']['preferences']
                     and case['process_id'] == case['process_id_after'], 'Dock observations incomplete')
                need(case['outside']['underlying_page_unchanged'] is True
                     and case['predictive_back']['underlying_page_unchanged'] is True,
                     'Outside or predictive Back dismissal failed')
                need([a['motion'] for a in case['automatic_appearance']] == ['OFF', 'SUBDUED'],
                     'Automatic appearance checks missing')
                for appearance in case['automatic_appearance']:
                    need(appearance['save_button_pressed'] is False
                         and appearance['persisted'] == appearance['away'] == appearance['returned'],
                         'Appearance was not automatically retained')
                captures.extend([case['outside'], *case['destinations']])
            for case in report['appearance_restart_cases']:
                need(case['force_stop_and_relaunch'] is True
                     and case['previous_process_id'] != case['restarted_process_id']
                     and case['save_button_pressed'] is False and case['server_mutations'] == 0
                     and case['after_restart']['writes'] == case['after_restore']['writes'] == 0
                     and case['after_restart']['preferences'] == case['persisted']
                     and case['before']['preferences'] == case['after_restore']['preferences']
                     and len(case['captures']) == 2, 'Appearance did not survive the actual process restart')
                captures.extend(case['captures'])
            for case in report['autosave_cases']:
                need(case['invalid_draft_retained'] is True and case['invalid_server_writes'] == 0
                     and case['invalid']['writes'] == case['invalid_after_navigation']['writes'] == 0
                     and case['server_mutations'] == case['saved']['writes'] == case['after']['writes'] == 2
                     and case['valid_horizon_months'] == 48 and case['confirmed_version'] == 4
                     and case['save_or_confirm_button_pressed'] is False
                     and case['navigation_preserved_saved_value'] is True and case['minimum_touch_dp'] == 48
                     and case['process_id'] == case['process_id_after'], 'Automatic strategy was not verified')
                captures.append(case)
            for capture in captures:
                filename = capture['screenshot']
                need(PurePosixPath(filename).name == filename and filename.endswith('.png'), 'Invalid capture reference')
                picture = read(folder + '/' + filename, root, 16 * 1024**2)
                need(picture.startswith(b'\x89PNG\r\n\x1a\n')
                     and sha(picture) == capture['screenshot_sha256'], 'Native screenshot changed')
                width, height = (int.from_bytes(picture[i:i+4], 'big') for i in (16, 20))
                need(0 < width < height and (width, height) == (capture['width'], capture['height']),
                     'Screenshot dimensions differ from live evidence')
                evidence[folder + '/' + filename] = picture
            for name, raw in ((f'controller/runtime-{page}.json', runtime_raw),
                (f'install-api37-{page}/install-results.json', installed_raw),
                (folder + '/design47-focused-observations.json', observations_raw)):
                evidence[name] = raw
            profiles[str(page)] = {'installation_sha256': sha(installed_raw),
                'runtime_sha256': sha(runtime_raw), 'observations_sha256': sha(observations_raw),
                'fonts': [1.0, 2.0], 'icons_per_font': 21, 'destinations_per_font': 6,
                'automatic_appearance': True, 'appearance_process_restart': True, 'automatic_strategy': True,
                'invalid_draft_retained': True, 'extra_server_writes_after_navigation': 0}
        for name, raw in evidence.items():
            need(envelope['files'][name] == {'bytes': len(raw), 'sha256': sha(raw)},
                 'Original evidence differs from the bound input envelope: ' + name)
    helper.verify_archive_file(path, item['sha256'], item['bytes'])
    return {**{key: item[key] for key in ('run_id', 'run_attempt', 'artifact_id')},
        'artifact_sha256': item['sha256'], 'artifact_bytes': item['bytes'],
        'build_provenance_sha256': sha(provenance_raw), 'summary_sha256': sha(summary_raw),
        'envelope_sha256': sha(envelope_raw), 'native_hook_sha256': expected['native_hook_sha256'],
        'profiles': profiles, 'design47_complete': True, 'original14_executed': False, 'full15_executed': False}


def validate(helper, native_helper, request):
    need(type(request) is dict and set(request) == {'schema', 'native_request', 'native_artifact'}
         and request['schema'] == 1, 'Unexpected delivery47 request')
    native_request, _ = helper.evidence(request, 'native_request')
    _, _, provenance, build_raw, export_raw, _ = native_helper.validate(native_request)
    build_request, _ = helper.evidence(native_request, 'build_request')
    build, exported = helper.decoded(build_raw), helper.decoded(export_raw)
    native = native_receipt(helper, request['native_artifact'], provenance, build)
    return {'request': build_request, 'build': build, 'export': exported, 'native': native,
            'build_report_sha256': sha(build_raw), 'build_export_receipt_sha256': sha(export_raw)}


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
            values = {44: 47, 43: 45}
            if verifier:
                values.update({29771254: binding["build"]["apks"][APK]["bytes"],
                               68927139: binding["export"]["bytes"]})
            value = values.get(value, value)
        elif type(value) is str:
            if verifier and value in identities:
                value = identities[value]
            else:
                for old, new in (("0.13.6-preview", "0.14.0-preview"), ("0.13.5-preview", "0.13.7-preview"),
                    ("upgrade43_to44", "upgrade45_to47"), ("upgrade44_bootstrap", "upgrade47_bootstrap"),
                    ("previous43", "previous45"), ("candidate44", "candidate47"),
                    ("preview44", "preview47"), ("PREVIEW44", "PREVIEW47"),
                    ("exact44", "exact47"), ("Analyst-AI-44-", "Analyst-AI-47-")):
                    value = value.replace(old, new)
        if value != node.value:
            replacements.append((node, repr(value)))
    return helper.edits(text, replacements)


def authorization(binding):
    build, exported, native = binding["build"], binding["export"], binding["native"]
    return {"kind": "owner_requested_latest_built_preview_delivery",
        "owner_request": "Продолжай и не забывай обновлять актуальную версию приложения на нашем сервере! Само рабочее приложение!",
        "date": build["finished_at"][:10], "package_name": PACKAGE, "version_code": 47,
        "apk_sha256": build["apks"][APK]["sha256"], "apk_bytes": build["apks"][APK]["bytes"],
        "certificate_sha256": CERT, "source_archive_sha256": exported["sha256"], "source_archive_bytes": exported["bytes"],
        "source_sha256": binding["request"]["source_sha256"], "source_backup_commit": binding["request"]["source_backup_commit"],
        "build_report_sha256": binding["build_report_sha256"], "build_export_receipt_sha256": binding["build_export_receipt_sha256"],
        "windows_run_id": build["github"]["run_id"], "windows_run_attempt": build["github"]["run_attempt"],
        "full_check_and_build_passed": True,
        "preview_install_smoke": {**native, "evidence_verified_at_workflow_preparation": True,
            "android_api": 37, "abi": "x86_64", "page_size_profiles": [16384, 4096],
            "previous45_clean_install": True, "upgrade45_to47": True, "upgrade47_bootstrap_launch": True,
            "candidate47_clean_install": True, "candidate47_bootstrap_launch": True,
            "physical_phone_verified": False, "full_runtime_matrix_passed": False},
        "design47_run_id": native["run_id"], "design47_status": "completed_diagnostic_only",
        "original14_status": "not_executed_in_design47_run", "full15_runtime_matrix_passed": False,
        "complete_release_gate_passed": False, "runtime_pass": False, "phone_verified": False,
        "reason_for_current_manifest_change": "Publish the exact latest built preview under the existing mandatory client update channel, as directly requested by the owner.",
        "database_mutations_performed": False, "session_or_owner_binding_mutations_performed": False,
        "backend_deployment_performed": False, "service_restart_performed": False,
        "signing_key_mutations_performed": False, "trading_orders_submitted": False, "paid_ai_calls_performed": False}


def render(helper, binding, request_sha):
    templates = {name: helper.checked_bytes(REFERENCE / name, expected).decode() for name, expected in TEMPLATES.items()}
    build, exported = binding["build"], binding["export"]
    run, attempt = build["github"]["run_id"], build["github"]["run_attempt"]
    text = literals(helper, templates["publish-preview44.py"], binding)
    for old, new in (("previous_is_exact43", "previous_is_exact45"), ("current_is_exact44", "current_is_exact47"),
                     ("exact44_reported_by_active_session=", "exact47_reported_by_active_session=")):
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
    text = helper.assign(text, "notes", repr("Тестовая версия 0.14.0-preview. Единое оформление, меню иконок по кнопке «мозг», анимированные частичные окна и автоматическое сохранение настроек. Полная проверка интерфейса продолжается."))
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
    workflow["name"] = "Deliver exact preview47 at the owner request"
    workflow["on"]["push"]["paths"] = [TARGET]
    job["steps"][1]["name"] = "Publish verified preview47 design and autosave; verify policy entire APK and health"
    job["steps"][1]["run"] = "python3 - <<'PY'\n" + hosted + "\nPY\n"
    for key in ("name", "path"):
        job["steps"][2]["with"][key] = job["steps"][2]["with"][key].replace("preview44", "preview47")
    raw_workflow = yaml.safe_dump(workflow, allow_unicode=True, sort_keys=False, width=120).encode()
    need(yaml.safe_load(raw_workflow) == workflow, "YAML roundtrip changed workflow")
    outputs = {"publish-preview47.py": text.encode(), "verify-public47.py": verifier.encode(),
        "remote-wrapper.py": remote.encode(), "hosted-delivery.py": hosted.encode(), "workflow.yml": raw_workflow}
    outputs["preparation.json"] = encoded({"schema": 1, "preparation_only": True, "request_sha256": request_sha,
        "target_workflow": TARGET, "source_backup_commit": binding["request"]["source_backup_commit"],
        "source_sha256": binding["request"]["source_sha256"], "native_evidence": binding["native"],
        "candidate": {"version_code": 47, "version_name": "0.14.0-preview", **build["apks"][APK]},
        "prior_channel": {"version_code": 45, "version_name": "0.13.7-preview", "bytes": PREVIOUS_BYTES, "sha256": PREVIOUS_SHA},
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
