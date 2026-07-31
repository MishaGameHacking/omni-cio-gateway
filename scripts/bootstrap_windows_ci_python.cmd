@echo off
setlocal EnableExtensions

set "PY_VERSION=3.12.10"
set "PY_HOME=C:\actions-runner\_tool\omni-python-%PY_VERSION%"
if not defined RUNNER_TEMP set "RUNNER_TEMP=%TEMP%"
set "PY_INSTALLER=%RUNNER_TEMP%\python-%PY_VERSION%-amd64.exe"
set "PY_INSTALL_LOG=%RUNNER_TEMP%\python-%PY_VERSION%-install.log"

if exist "%PY_HOME%\python.exe" goto verify_python

curl.exe --fail --location --silent --show-error --proto "=https" --tlsv1.2 --output "%PY_INSTALLER%" "https://www.python.org/ftp/python/%PY_VERSION%/python-%PY_VERSION%-amd64.exe"
if errorlevel 1 exit /b 10

powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$signature = Get-AuthenticodeSignature -LiteralPath '%PY_INSTALLER%'; if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') { Write-Error 'Python installer signature validation failed.'; exit 1 }"
if errorlevel 1 exit /b 11

if exist "%PY_HOME%" rmdir /s /q "%PY_HOME%"

"%PY_INSTALLER%" /quiet InstallAllUsers=0 TargetDir="%PY_HOME%" Include_launcher=0 Include_test=0 Include_doc=0 Include_tcltk=0 Shortcuts=0 AssociateFiles=0 PrependPath=0 AppendPath=0 Include_pip=1 Include_dev=1 Include_tools=1 /log "%PY_INSTALL_LOG%"
if errorlevel 1 (
  if exist "%PY_INSTALL_LOG%" type "%PY_INSTALL_LOG%"
  exit /b 12
)

:verify_python
"%PY_HOME%\python.exe" -c "import sys; assert sys.version_info[:3] == (3, 12, 10); print(sys.version)"
if errorlevel 1 exit /b 13

"%PY_HOME%\python.exe" -m pip --version
if errorlevel 1 exit /b 14

if defined GITHUB_PATH (
  >>"%GITHUB_PATH%" echo %PY_HOME%
  >>"%GITHUB_PATH%" echo %PY_HOME%\Scripts
)

echo Python CI runtime ready: %PY_HOME%
exit /b 0
