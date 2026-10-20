"""Resolve current-platform fixture contracts without relaxing any assertion."""
from __future__ import annotations
import subprocess
from migrate_android17 import BRANCH, ROOT, Changes
from migrate_android17_contract import replace_function


def main():
    branch = subprocess.check_output(['git', 'symbolic-ref', '--short', 'HEAD'], cwd=ROOT, text=True).strip()
    if branch != BRANCH:
        raise ValueError('Dedicated review branch required')
    changes = Changes(ROOT)
    path = 'backend/tests/test_client_updates.py'
    changes.optional(path, 'self.assertRaises(ReleaseUnavailable)', 'self.assertRaises(updates.ReleaseUnavailable)')
    changes.replace(path, 'result.min_android_api', 'result.min_sdk')
    replace_function(changes, path, 'evidence', '''
        def evidence(self, version=23):
            sha = hashlib.sha256(self.apk.read_bytes()).hexdigest()
            return publication_report({
                'sha256': sha, 'bytes': self.apk.stat().st_size, 'certificate_sha256': CERT,
                'signature_v2': True, 'zipalign_16kb': True, 'test_only': False, 'debuggable': False,
                'package': 'ru.omnicio.app.debug', 'version_code': version,
                'version_name': '0.6.0-preview',
            })
    ''')
    path = 'backend/tests/test_release_runtime_publication.py'
    changes.replace(path, 'result.min_android_api', 'result.min_sdk')
    path = 'backend/tests/test_release_rollover.py'
    replace_function(changes, path, 'report', '''
        def report(self, version=23, certificate=CERT):
            sha = hashlib.sha256(self.apk.read_bytes()).hexdigest()
            return publication_report(dict(
                sha256=sha, bytes=self.apk.stat().st_size, certificate_sha256=certificate,
                signature_v2=True, zipalign_16kb=True, debuggable=False, test_only=False,
                package=PACKAGE, version_code=version, version_name=f'test-{version}',
            ))
    ''')
    # Mutate metadata that is valid under the new floor but cannot change for an
    # already published version. Old test set min_sdk to 37, now a no-op.
    changes.replace(path, "report['min_sdk'] = 37", "report['version_name'] = 'changed-same-code'")
    path = 'docs/ANDROID17_MIGRATION.md'
    changes.replace(path, 'rather\n  than relying on an application flag ignored for the new target.',
                    'following the platform migration recommendation. This is not a claim\n  that the application flag is ignored on API37.')
    changes.finish()


if __name__ == '__main__':
    main()
