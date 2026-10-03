@echo off
setlocal EnableExtensions

set "PYTHON_ARCHIVE_URL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.zip"
set "PYTHON_ARCHIVE_SHA256=8649692de846c56a7189d6dae5c322ab20deb1b5908b6f39426b62a36f39415d"
set "PYTHON_HOME=%RUNNER_TOOL_CACHE%\omnicio-python-3.12.10"
set "PYTHON_EXE=%PYTHON_HOME%\python.exe"
set "PYTHON_ARCHIVE=%RUNNER_TEMP%\python-3.12.10-amd64.zip"

if not defined GITHUB_ENV (
  echo ::error::GITHUB_ENV is required to bootstrap the self-hosted Python runtime.
  exit /b 1
)
if not defined RUNNER_TOOL_CACHE (
  echo ::error::RUNNER_TOOL_CACHE is required to bootstrap the self-hosted Python runtime.
  exit /b 1
)
if not defined RUNNER_TEMP (
  echo ::error::RUNNER_TEMP is required to bootstrap the self-hosted Python runtime.
  exit /b 1
)

if not exist "%PYTHON_EXE%" (
  where curl.exe >nul 2>nul
  if errorlevel 1 (
    echo ::error::curl.exe is required to bootstrap the pinned Python runtime.
    exit /b 1
  )

  echo Downloading pinned CPython 3.12.10 from python.org...
  curl.exe --fail --location --retry 3 --retry-delay 2 ^
    --output "%PYTHON_ARCHIVE%" "%PYTHON_ARCHIVE_URL%"
  if errorlevel 1 exit /b 1

  certutil -hashfile "%PYTHON_ARCHIVE%" SHA256 | findstr /i /c:"%PYTHON_ARCHIVE_SHA256%" >nul
  if errorlevel 1 (
    echo ::error::Downloaded Python archive failed SHA256 verification.
    del /q "%PYTHON_ARCHIVE%" 2>nul
    exit /b 1
  )

  if exist "%PYTHON_HOME%" rmdir /s /q "%PYTHON_HOME%"
  mkdir "%PYTHON_HOME%"
  if errorlevel 1 exit /b 1

  powershell.exe -NoLogo -NoProfile -NonInteractive -Command ^
    "Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory($env:PYTHON_ARCHIVE, $env:PYTHON_HOME)"
  if errorlevel 1 exit /b 1

  del /q "%PYTHON_ARCHIVE%" 2>nul
)

"%PYTHON_EXE%" -c "import sys; assert sys.version_info[:2] == (3, 12); print(sys.version)"
if errorlevel 1 exit /b 1

"%PYTHON_EXE%" -m pip --version >nul 2>nul
if errorlevel 1 (
  "%PYTHON_EXE%" -m ensurepip --upgrade
  if errorlevel 1 exit /b 1
)

"%PYTHON_EXE%" -m venv .venv-ci
if errorlevel 1 exit /b 1

set "VENV_PYTHON=%CD%\.venv-ci\Scripts\python.exe"
"%VENV_PYTHON%" -c "import sys; assert sys.version_info[:2] == (3, 12); print(sys.version)"
if errorlevel 1 exit /b 1

>>"%GITHUB_ENV%" echo OMNICIO_PYTHON=%VENV_PYTHON%
>>"%GITHUB_ENV%" echo PIP_CACHE_DIR=%RUNNER_TOOL_CACHE%\omnicio-pip-cache
