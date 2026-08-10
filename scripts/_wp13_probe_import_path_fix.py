from pathlib import Path

path = Path("infrastructure/windows/rehearse_wp13_persistence.ps1")
text = path.read_text(encoding="utf-8")
old = '''    $oldDsn = $env:OMNI_CIO_WP13_DSN
    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()
    try {
        $env:OMNI_CIO_WP13_DSN = (
            "host=127.0.0.1 port=$Port user=wp13_owner " +
            "dbname=$DatabaseName connect_timeout=5"
        )
'''
new = '''    $oldDsn = $env:OMNI_CIO_WP13_DSN
    $oldPythonPath = $env:PYTHONPATH
    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()
    try {
        $env:OMNI_CIO_WP13_DSN = (
            "host=127.0.0.1 port=$Port user=wp13_owner " +
            "dbname=$DatabaseName connect_timeout=5"
        )
        if ([string]::IsNullOrWhiteSpace($oldPythonPath)) {
            $env:PYTHONPATH = $RepoRoot
        }
        else {
            $env:PYTHONPATH = "$RepoRoot;$oldPythonPath"
        }
'''
if old not in text:
    raise SystemExit("probe environment anchor not found")
text = text.replace(old, new, 1)
old_finally = '''    finally {
        $env:OMNI_CIO_WP13_DSN = $oldDsn
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}
'''
new_finally = '''    finally {
        $env:OMNI_CIO_WP13_DSN = $oldDsn
        $env:PYTHONPATH = $oldPythonPath
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}
'''
if old_finally not in text:
    raise SystemExit("probe cleanup anchor not found")
text = text.replace(old_finally, new_finally, 1)
path.write_text(text, encoding="utf-8", newline="\n")
