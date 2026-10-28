"""Normalize one escaped regex literal in the one-shot staging patcher."""
from pathlib import Path

path = Path(".github/scripts/apply_sonar_staging_patches.py")
value = path.read_text(encoding="utf-8")
old = """    ('r"[0-9](?:\\\\.[0-9]{1,3})?"', 'r"\\\\d(?:\\\\.\\\\d{1,3})?"'),"""
new = """    ('r"[0-9](?:\\.[0-9]{1,3})?"', 'r"\\\\d(?:\\.\\\\d{1,3})?"'),"""
if value.count(old) != 1:
    raise RuntimeError("escaped theme regex patch entry changed")
path.write_text(value.replace(old, new), encoding="utf-8")
