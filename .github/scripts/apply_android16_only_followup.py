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
    ".github/scripts/tests/test_build_release_manifest.py",
    '"min_sdk": 33,',
    '"min_sdk": 36,',
)
replace_once(
    ".github/scripts/tests/test_distributable_apk_workflow.py",
    "self.assertEqual(self.action.count('--previous \"%PREVIOUS_APK%\"'), 2)",
    "self.assertEqual(self.action.count('--previous \"%PREVIOUS_APK%\"'), 1)",
)
