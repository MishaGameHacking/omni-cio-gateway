"""Prepare the bounded recovery operation for the unchanged reviewed owner transport."""
import json
from pathlib import Path


def main():
    destination = Path('deploy/plan-20261027')
    if not destination.is_dir() or destination.is_symlink():
        raise RuntimeError('transport_directory_missing')
    (destination / 'operation.py').write_bytes(Path('deploy/runtime_recovery.py').read_bytes())
    (destination / 'payload.json').write_text(json.dumps({
        'source_commit': 'af95e8de8cfd50970d712483b8c17e866f7239c9'}))


if __name__ == '__main__':
    main()
