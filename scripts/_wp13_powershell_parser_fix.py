from pathlib import Path

path = Path("infrastructure/windows/rehearse_wp13_persistence.ps1")
text = path.read_text(encoding="utf-8")
old = '$reasonCode = "WP13_AUDIT_ERROR:$exceptionType:$errorId"'
new = '$reasonCode = "WP13_AUDIT_ERROR:${exceptionType}:${errorId}"'
if old not in text:
    raise SystemExit("safe error classification interpolation not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
