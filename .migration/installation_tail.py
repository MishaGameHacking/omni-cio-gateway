def _one_emulator(run: dict, digest: str, target) -> dict:
    if run.get('abi') != 'x86_64' or run.get('profile_ui_required') is not True:
        raise InstallationEvidenceError('unrecognized_emulator_evidence')
    records = _results(run.get('results'))
    required = {'candidate_clean_install', 'previous_clean_install', 'upgrade_to_candidate',
                'upgrade_bootstrap_launch', 'debug_ui_fixture_install', 'profile_ui', 'kernel_page_size'}
    launches = {'activity_launch', 'bootstrap_activity_launch'} & records.keys()
    if not required <= records.keys() or len(launches) != 1 or set(records) != required | launches:
        raise InstallationEvidenceError('installation_evidence_incomplete')
    for name in {'candidate_clean_install', 'upgrade_to_candidate', 'upgrade_bootstrap_launch'} | launches:
        if _digest(records[name].get('apk_sha256')) != digest:
            raise InstallationEvidenceError('installation_artifact_mismatch')
    if _digest(records['previous_clean_install'].get('apk_sha256')) == digest:
        raise InstallationEvidenceError('upgrade_reinstalled_same_artifact')
    counts = validate_ui_receipt(records['profile_ui'], records['debug_ui_fixture_install'].get('apk_sha256'))
    kernel = records['kernel_page_size']
    expected = {'android_api': target.api, 'runtime_case': target.key, 'abi': 'x86_64',
                'system_image': target.system_image, 'page_size_bytes': target.page_size_bytes,
                'command': 'getconf PAGE_SIZE'}
    if any(type(kernel.get(key)) is not type(value) or kernel[key] != value
           for key, value in expected.items()):
        raise InstallationEvidenceError('invalid_kernel_page_size_evidence')
    if _digest(kernel.get('apk_sha256')) != digest:
        raise InstallationEvidenceError('installation_artifact_mismatch')
    return {'clean_install': True, 'upgrade': True, 'upgrade_launch': True, 'launch': True,
            **counts, 'page_size_bytes': target.page_size_bytes, 'system_image': target.system_image,
            'runtime_16kb': target.page_size_bytes == 16_384}


def from_ci_reports(installations: object, apk_sha256: str) -> dict:
    """Require both independently measured Android 17 page-size cases.

    Historical reports are not accepted as proof for the supported platform.
    """
    from .android_platform import RUNTIME_SCHEMA, RUNTIME_TARGETS, runtime_target
    digest = _digest(apk_sha256)
    if not isinstance(installations, list) or len(installations) != len(RUNTIME_TARGETS):
        raise InstallationEvidenceError('android_17_runtime_matrix_required')
    result = {'apk_sha256': digest, 'runtime_schema': RUNTIME_SCHEMA}
    for run in installations:
        if not isinstance(run, dict):
            raise InstallationEvidenceError('invalid_emulator_report')
        try:
            target = runtime_target(run.get('android_api'), run.get('page_size_bytes'))
        except ValueError as error:
            raise InstallationEvidenceError('unsupported_emulator_runtime') from error
        if run.get('runtime_case') != target.key or target.key in result:
            raise InstallationEvidenceError('ambiguous_runtime_case')
        result[target.key] = _one_emulator(run, digest, target)
    if {target.key for target in RUNTIME_TARGETS} != set(result) - {'apk_sha256', 'runtime_schema'}:
        raise InstallationEvidenceError('android_17_runtime_matrix_required')
    return result
