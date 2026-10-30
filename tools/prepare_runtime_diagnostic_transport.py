"""Prepare the read-only operation for the unchanged reviewed owner transport."""
import json
from pathlib import Path


def main():
    destination = Path('deploy/plan-20261027')
    if not destination.is_dir() or destination.is_symlink():
        raise RuntimeError('transport_directory_missing')
    (destination / 'operation.py').write_bytes(Path('deploy/runtime_diagnostic.py').read_bytes())
    (destination / 'payload.json').write_text(json.dumps({
        'source_commit': 'cc22cb7ee3fe82eca28e4162e13c4463cab5ddc4'}))


if __name__ == '__main__':
    main()
