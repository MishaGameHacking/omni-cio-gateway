@echo off
setlocal
set "project=%~dp0omni-cio-gateway"
if not exist "%project%\AGENTS.md" goto missing
cd /d "%project%" || exit /b 1
rem Trust only the reviewed workstation project, for this process and its children.
if defined GIT_CONFIG_COUNT goto scoped
set "GIT_CONFIG_COUNT=1"
set "GIT_CONFIG_KEY_0=safe.directory"
set "GIT_CONFIG_VALUE_0=%project:\=/%"
:scoped
set "prompt=Read the current Lenovo notes at the top of AGENTS.md. Check AnalystAIHomeHost and the protected Linux API on port 18158. If registration is pending, use the verified local AnalystAI-Linux Start.cmd. Continue the Analyst AI development here. Reply in Russian."
if exist "%LOCALAPPDATA%\Programs\OpenAI\Codex\bin\codex.exe" (
  "%LOCALAPPDATA%\Programs\OpenAI\Codex\bin\codex.exe" "%prompt%"
  exit /b
)
where.exe codex >nul 2>nul
if errorlevel 1 goto desktop
call codex "%prompt%"
exit /b
:desktop
echo Open this local project in your installed Codex desktop app or IDE:
echo %project%
explorer.exe "%project%"
pause
exit /b 0
:missing
echo The verified Analyst AI project is not available here.
pause
exit /b 1
