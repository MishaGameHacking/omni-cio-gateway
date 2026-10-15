from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(relative: str, old: str, new: str) -> None:
    target = ROOT / relative
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative}: expected one match, found {count}: {old!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


replace_once(
    "backend/release_publication.py",
    "    if report.get('min_sdk') != 36:\n"
    "        raise ReleaseUnavailable('unsupported_android_floor')\n",
    "    minimum_sdk = report.get('min_sdk')\n"
    "    if type(minimum_sdk) is not int or minimum_sdk < 36:\n"
    "        raise ReleaseUnavailable('unsupported_android_floor')\n",
)
replace_once(
    "backend/tests/test_update_integration.py",
    "'min_sdk':33,",
    "'min_sdk':36,",
)
replace_once(
    "backend/tests/test_release_recovery.py",
    "report['min_sdk'] = 34",
    "report['min_sdk'] = 37",
)
replace_once(
    "backend/tests/test_release_rollover.py",
    "report['min_sdk'] = 34",
    "report['min_sdk'] = 37",
)

stale = []
pattern = re.compile(r"min_sdk\s*['\"]?\s*[:=]\s*33\b")
for candidate in sorted((ROOT / "backend").rglob("*.py")):
    text = candidate.read_text(encoding="utf-8")
    if pattern.search(text):
        stale.append(candidate.relative_to(ROOT).as_posix())
if stale:
    raise RuntimeError("Android 13 publication fixtures remain: " + ", ".join(stale))

Path(__file__).unlink()
