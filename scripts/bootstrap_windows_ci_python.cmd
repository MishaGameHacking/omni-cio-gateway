@echo off
setlocal EnableExtensions

set "PY_VERSION=3.12.10"
set "PY_SHA256=8649692de846c56a7189d6dae5c322ab20deb1b5908b6f39426b62a36f39415d"
set "PY_HOME=C:\actions-runner\_tool\omni-python-%PY_VERSION%"
set "GIT_BASH_HOME=C:\Program Files\Git\bin"
if not defined RUNNER_TEMP set "RUNNER_TEMP=%TEMP%"
set "PY_ARCHIVE=%RUNNER_TEMP%\python-%PY_VERSION%-amd64.zip"

if not exist "%GIT_BASH_HOME%\bash.exe" exit /b 9
if exist "%PY_HOME%\python.exe" goto verify_python

curl.exe --fail --location --silent --show-error --proto "=https" --tlsv1.2 --output "%PY_ARCHIVE%" "https://www.python.org/ftp/python/%PY_VERSION%/python-%PY_VERSION%-amd64.zip"
if errorlevel 1 exit /b 10

certutil.exe -hashfile "%PY_ARCHIVE%" SHA256 | findstr /I /C:"%PY_SHA256%" >nul
if errorlevel 1 exit /b 11

if exist "%PY_HOME%" rmdir /s /q "%PY_HOME%"
mkdir "%PY_HOME%"
if errorlevel 1 exit /b 12

tar.exe -xf "%PY_ARCHIVE%" -C "%PY_HOME%"
if errorlevel 1 exit /b 13

"%PY_HOME%\python.exe" -m ensurepip --upgrade
if errorlevel 1 exit /b 14

:verify_python
"%PY_HOME%\python.exe" -c "import sys; assert sys.version_info[:3] == (3, 12, 10); print(sys.version)"
if errorlevel 1 exit /b 15

"%PY_HOME%\python.exe" -m pip --version
if errorlevel 1 exit /b 16

if defined GITHUB_PATH (
  >>"%GITHUB_PATH%" echo %GIT_BASH_HOME%
  >>"%GITHUB_PATH%" echo %PY_HOME%
  >>"%GITHUB_PATH%" echo %PY_HOME%\Scripts
)

echo Git Bash ready: %GIT_BASH_HOME%
echo Python CI runtime ready: %PY_HOME%
exit /b 0
