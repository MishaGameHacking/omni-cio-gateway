"""Execute the audited Bash repair without mutating readonly shell constants.

Bash treats ``NAME=value command`` as an assignment in the current shell before
starting the command. That fails when NAME was intentionally marked readonly,
even when the assigned value is identical. The repair script needs those values
only in the child Python process, so stage an exact, bounded transformation that
uses the external ``env`` command instead. All hard-coded server and artifact
constants remain readonly in the parent script and in the remote rollback script.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".github/scripts/repair_moscow_update_channel.sh"

REPLACEMENTS = {
    '    SERVER_ID="$SERVER_ID" SSH_KEY_ID="$SSH_KEY_ID" "${PYTHON_CMD[@]}" - <<\'PY\'':
        '    env SERVER_ID="$SERVER_ID" SSH_KEY_ID="$SSH_KEY_ID" "${PYTHON_CMD[@]}" - <<\'PY\'',
    'APK_PATH="$APK_UNIX" REPORT_PATH="$REPORT_UNIX" MANIFEST_PATH="$MANIFEST_PATH" \\\n':
        'env APK_PATH="$APK_UNIX" REPORT_PATH="$REPORT_UNIX" MANIFEST_PATH="$MANIFEST_PATH" \\\n',
    'SSH_PUBLIC_KEY_PATH="$SSH_PUBLIC_KEY_PATH" STATE_PATH="$STATE_PATH_FOR_PY" \\\n':
        'env SSH_PUBLIC_KEY_PATH="$SSH_PUBLIC_KEY_PATH" STATE_PATH="$STATE_PATH_FOR_PY" \\\n',
    'POLICY_PATH="$READBACK_POLICY" PACKAGE_NAME="$PACKAGE_NAME" RELEASE_FILENAME="$RELEASE_FILENAME" \\\n':
        'env POLICY_PATH="$READBACK_POLICY" PACKAGE_NAME="$PACKAGE_NAME" RELEASE_FILENAME="$RELEASE_FILENAME" \\\n',
}


def patched_source() -> str:
    text = SOURCE.read_text(encoding="utf-8")
    for original, replacement in REPLACEMENTS.items():
        count = text.count(original)
        if count != 1:
            raise RuntimeError(
                f"repair source invariant changed for {original[:48]!r}: expected 1, found {count}"
            )
        text = text.replace(original, replacement, 1)
    if text.count("env ") < len(REPLACEMENTS):
        raise RuntimeError("repair child environments were not staged")
    return text


def main() -> int:
    runner_temp = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
    runner_temp.mkdir(parents=True, exist_ok=True)
    destination = runner_temp / f"analyst-ai-repair-{os.environ.get('GITHUB_RUN_ID', 'local')}.sh"
    destination.write_text(patched_source(), encoding="utf-8", newline="\n")
    try:
        subprocess.run(["bash", "-n", str(destination)], check=True)
        completed = subprocess.run(["bash", str(destination)], check=False)
        return completed.returncode
    finally:
        destination.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
