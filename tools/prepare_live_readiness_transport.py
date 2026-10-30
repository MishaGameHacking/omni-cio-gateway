"""Bind the reviewed probe to the existing venv and administrative transport."""
import hashlib
import json
from pathlib import Path


def main():
    source = Path('deploy/live_readiness_audit.py').read_text()
    digest = hashlib.sha256(source.encode()).hexdigest()
    operation = '''import hashlib,json,subprocess
source = SOURCE_LITERAL
if hashlib.sha256(source.encode()).hexdigest() != DIGEST_LITERAL:
    raise RuntimeError('audit_source_changed')
result = subprocess.run(['/opt/analyst-ai/venv/bin/python', '-I', '-c', source],
    input=str(ENVELOPE['run_id']).encode(), capture_output=True, timeout=200)
if len(result.stdout) > 32000:
    raise RuntimeError('audit_output_exceeded')
try:
    receipt = json.loads(result.stdout)
except ValueError:
    raise RuntimeError('audit_receipt_unavailable') from None
print(json.dumps(receipt), flush=True)
if result.returncode:
    raise RuntimeError('live_readiness_audit_failed')
'''.replace('SOURCE_LITERAL', repr(source)).replace('DIGEST_LITERAL', repr(digest))
    destination = Path('deploy/plan-20261027')
    if not destination.is_dir() or destination.is_symlink():
        raise RuntimeError('transport_directory_missing')
    (destination / 'operation.py').write_text(operation)
    (destination / 'payload.json').write_text(json.dumps({'read_only': True, 'source_sha256': digest}))


if __name__ == '__main__':
    main()
