"""Normalize exact one-shot patcher literals before applying source changes."""
from pathlib import Path

patcher = Path(".github/scripts/apply_sonar_staging_patches.py")
value = patcher.read_text(encoding="utf-8")
old = """    ('r"[0-9](?:\\\\.[0-9]{1,3})?"', 'r"\\\\d(?:\\\\.\\\\d{1,3})?"'),"""
new = """    ('r"[0-9](?:\\.[0-9]{1,3})?"', 'r"\\\\d(?:\\.\\\\d{1,3})?"'),"""
if value.count(old) != 1:
    raise RuntimeError("escaped theme regex patch entry changed")
value = value.replace(old, new)

start_marker = 'old = """                foreground, background = ("disabledInk", "disabledContainer")'
end_marker = r'value = value.replace(old, "                foreground, background = _switch_roles(checked, enabled)\n")' + "\n"
end_marker = end_marker.replace('\\"', '"')
start = value.find(start_marker)
end = value.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError("theme nested switch patch block changed")
value = value[:start] + value[end + len(end_marker):]
patcher.write_text(value, encoding="utf-8")

source = Path(".github/scripts/theme_state_evidence.py")
lines = source.read_text(encoding="utf-8").splitlines()
indices = [index for index, line in enumerate(lines)
           if line.strip().startswith('foreground, background = ("disabledInk", "disabledContainer")')]
if len(indices) != 1:
    raise RuntimeError("theme nested switch source changed")
index = indices[0]
if index + 1 >= len(lines) or lines[index + 1].strip() != '(("onPrimary", "primary") if checked else ("outline", "surfaceContainerHighest"))':
    raise RuntimeError("theme nested switch continuation changed")
indent = lines[index][:-len(lines[index].lstrip())]
lines[index:index + 2] = [indent + "foreground, background = _switch_roles(checked, enabled)"]
source.write_text("\n".join(lines) + "\n", encoding="utf-8")
