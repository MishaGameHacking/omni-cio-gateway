"""Prepare the explicitly requested intermediate47 without claiming native acceptance.

Owner instruction on 26 October: use Timeweb, publish the working update now,
do not repeat the full checks. Exact successful build, signing, atomic channel
publication and complete public APK verification remain mandatory here.
The stricter complete-native publication preparer remains unchanged.
"""
from pathlib import Path
import argparse
import ast
import hashlib
import importlib.util
import json

HERE = Path(__file__).resolve().parent
CONTEXT = HERE.parents[1]
PIN = 'd047e30186927c342868e0dad6777a305938f0e723fda89029bd30c72a60b20d'
OWNER_REQUEST = 'Вся работа на ноуте и на исходный код приложения и его апк на Timeweb; новое обновление без повторной полной проверки'


def load():
    path = HERE / 'prepare_delivery47.py'
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PIN
    ast.parse(raw)
    spec = importlib.util.spec_from_file_location('strict47_publication_text_renderer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    publisher = load()
    helper, build_verifier = publisher.helpers()
    raw = helper.checked_bytes(helper.path_under_context(args.request), args.request_sha256)
    request = helper.decoded(raw)
    assert set(request) == {'schema', 'build_binding', 'owner_requested_intermediate_without_full_native'}
    assert request['schema'] == 1 and request['owner_requested_intermediate_without_full_native'] is True
    build_binding, _ = helper.evidence(request, 'build_binding')
    _, _, provenance, build_raw, export_raw, _ = build_verifier.validate(build_binding)
    build_request, _ = helper.evidence(build_binding, 'build_request')
    build, exported = helper.decoded(build_raw), helper.decoded(export_raw)
    assert build['github']['run_id'] == 40392908825
    native = {'status': 'not_executed_for_published_build', 'run_id': None,
              'full_runtime_matrix_passed': False, 'physical_phone_verified': False}
    binding = {'request': build_request, 'build': build, 'export': exported,
               'native': native, 'build_report_sha256': publisher.sha(build_raw),
               'build_export_receipt_sha256': publisher.sha(export_raw)}
    original_authorization = publisher.authorization

    def authorization(value):
        result = original_authorization(value)
        result.update(owner_request=OWNER_REQUEST, explicit_intermediate_preview=True,
            source_archive_reexport=exported.get('reexport'),
            preview_install_smoke=native,
            design47_run_id=None, design47_status='not_executed_for_published_build',
            original14_status='not_executed_for_published_build',
            prior_native_attempt={'run_id': 40389869187, 'build_run_id': 40386457173,
                'status': 'failed', 'artifact_id': 12685050936,
                'artifact_sha256': '9f8dc6419f23bcaf4fd964684582dcf7920fae9a0394aba44555cdd7c7869762',
                'is_evidence_for_published_build': False},
            reason_for_current_manifest_change='Owner explicitly requests an intermediate Timeweb update without another full native matrix; previous failures remain failures.')
        return result

    publisher.authorization = authorization
    outputs = publisher.render(helper, binding, publisher.sha(raw))
    preparation = json.loads(outputs['preparation.json'])
    preparation['owner_requested_intermediate_without_full_native'] = True
    preparation['authorization'] = authorization(binding)
    preparation['strict_native_preparer_unchanged_sha256'] = PIN
    outputs['preparation.json'] = publisher.encoded(preparation)
    destination = helper.path_under_context(args.output)
    assert destination.parent == HERE.parent and not destination.exists()
    destination.mkdir()
    for name, content in outputs.items():
        (destination / name).write_bytes(content)
    print(json.dumps({'prepared_only': str(destination),
        'workflow_sha256': publisher.sha(outputs['workflow.yml']),
        'version': 47, 'full_build_passed': True, 'native_acceptance': False,
        'publication_performed': False}))


if __name__ == '__main__':
    main()
