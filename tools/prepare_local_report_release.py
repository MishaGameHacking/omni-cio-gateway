"""Verify the exact two-file WSL artifact and reuse the pinned release/rollback implementation."""
import hashlib
import os
from pathlib import Path

import prepare_gpt6_protocol_transport as validation

BASE="68e0fb73feddf178c29d990633edae42aa7adda3"
SOURCE="853090e11dcefef693366159c97316e55045c4c9"
RUN="41088491538"
ARTIFACT="34a1f99d1ef04784be4f939deaac2a8ba14dfc38c20ac310c03c09a8cce91cbd"
BUNDLE="4c45834b29bdedd6ccc3c7d120f133423e11b2d6c611b6c9e9d0d09b3debcc3c"
CORE_HASH="30671a47f3de7f68ffa00c37cda262afb7c2dc5c5ae5c1180baa36d7613068fc"
VALIDATOR_HASH="3e2ac9c47cd64076a2d376499a47df8026210cca5a8e7988d6be09514c44240a"


def operation(core, extension):
    validation.require(hashlib.sha256(core).hexdigest()==CORE_HASH,"pinned_rollback_core_changed")
    # The transport carries one self-contained script. Install the pinned module
    # in memory under its normal import name; its old command entry is never run.
    return ("import types,sys\nmod=types.ModuleType('gpt6_protocol_release')\n"
            "sys.modules[mod.__name__]=mod\nexec(compile("+repr(core.decode())+",'pinned-release-core','exec'),mod.__dict__)\n"
            "exec(compile("+repr(extension.decode())+",'local-report-release','exec'),globals())\n").encode()


def main():
    validation.require(hashlib.sha256(Path('tools/prepare_gpt6_protocol_transport.py').read_bytes()).hexdigest()==VALIDATOR_HASH,
                       "pinned_artifact_verifier_changed")
    old_base,old_modules=validation.BASE,validation.MODULES
    validation.BASE,validation.MODULES=BASE,{"osint_worker.py","local_research.py"}
    try:
        payload=validation.verify_artifact(Path(os.environ['RUNNER_TEMP'])/'server-runtime-artifact.zip',
            archive_sha=ARTIFACT,bundle_sha=BUNDLE,source_sha=SOURCE,run_id=RUN)
    finally:
        validation.BASE,validation.MODULES=old_base,old_modules
    target=Path('deploy/plan-20261027')
    validation.require(target.is_dir() and not target.is_symlink(),'transport_directory_missing')
    script=operation(Path('deploy/gpt6_protocol_release.py').read_bytes(),Path('deploy/local_report_route_release.py').read_bytes())
    (target/'payload.json').write_bytes(payload)
    (target/'operation.py').write_bytes(script)


if __name__=='__main__':
    main()
