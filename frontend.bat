@echo off
REM ==========================================================================
REM  SAWIE frontend launcher (Windows 10/11). Double-click to run.
REM  1. check Node 22.12+ and npm   2. npm install when needed
REM  3. make sure the backend is up (starts backend.bat in a new window if not)
REM  4. start Vite on port 5173 and open http://localhost:5173 in the browser
REM ==========================================================================
setlocal EnableExtensions
title SAWIE frontend
cd /d "%~dp0"

set "ROOT=%~dp0"
set "FRONTEND=%ROOT%frontend"
set "HEALTH=http://127.0.0.1:8000/api/health"
set "APP_URL=http://localhost:5173"
set "SETUP_FLAG=%ROOT%backend\.setup_in_progress"
set "LOCK_MARKER=%FRONTEND%\node_modules\.lock_hash"

echo.
echo  SAWIE frontend
echo  --------------
echo.

REM ---- 1. Node.js 22.12+ and npm ---------------------------------------------
where node >nul 2>&1
if errorlevel 1 (
  echo  [ERROR] Node.js was not found.
  echo.
  echo  Install the LTS version from https://nodejs.org/ ^(this also installs npm^),
  echo  then double-click frontend.bat again.
  goto :fail
)
node -e "const [a,b]=process.versions.node.split('.').map(Number);process.exit(a>22||(a===22&&b>=12)?0:1)"
if errorlevel 1 (
  for /f "delims=" %%V in ('node -v') do echo  [ERROR] Node.js %%V is too old. Version 22.12 or newer is required.
  echo  Install the LTS version from https://nodejs.org/ and try again.
  goto :fail
)
where npm >nul 2>&1
if errorlevel 1 (
  echo  [ERROR] npm was not found. Reinstall Node.js from https://nodejs.org/
  goto :fail
)
for /f "delims=" %%V in ('node -v') do echo  [ok] Node.js %%V
for /f "delims=" %%V in ('call npm -v') do echo  [ok] npm %%V

REM ---- 2. Dependencies -----------------------------------------------------
cd /d "%FRONTEND%"
for /f "delims=" %%H in ('node scripts\hash-file.mjs package-lock.json') do set "LOCKHASH=%%H"
set "OLDLOCK="
if exist "%LOCK_MARKER%" set /p OLDLOCK=<"%LOCK_MARKER%"
set "NEED_INSTALL="
if not exist "node_modules" set "NEED_INSTALL=1"
if /i not "%LOCKHASH%"=="%OLDLOCK%" set "NEED_INSTALL=1"
if defined NEED_INSTALL (
  echo  [..] Installing frontend dependencies. The first run takes a few minutes.
  call npm install --no-audit --no-fund
  if errorlevel 1 (
    echo.
    echo  [ERROR] npm install failed. Check the internet connection and the messages above.
    goto :fail
  )
  for /f "delims=" %%H in ('node scripts\hash-file.mjs package-lock.json') do set "LOCKHASH=%%H"
)
if defined NEED_INSTALL (
  > "%LOCK_MARKER%" echo %LOCKHASH%
  echo  [ok] Dependencies installed
) else (
  echo  [ok] Dependencies up to date
)
if not exist ".env" if exist ".env.example" copy /y ".env.example" ".env" >nul

REM ---- 3. Backend first ---------------------------------------------------
echo  [..] Checking the backend at %HEALTH%
set /a TRIES=0
:quick_poll
node scripts\probe.mjs %HEALTH%
if not errorlevel 1 goto :backend_ready
set /a TRIES+=1
if %TRIES% GEQ 3 goto :start_backend
timeout /t 1 /nobreak >nul
goto :quick_poll

:start_backend
echo  [..] The backend is not running. Starting backend.bat in a new window.
start "SAWIE backend" "%ROOT%backend.bat"
set /a WAITED=0
set /a SETUP_WAITED=0
:slow_poll
timeout /t 1 /nobreak >nul
node scripts\probe.mjs %HEALTH%
if not errorlevel 1 goto :backend_ready
REM First run: while the backend is still installing Python packages, that time
REM does not count against the 60 second limit; give up after 15 minutes instead.
if exist "%SETUP_FLAG%" (
  set /a SETUP_WAITED+=1
  goto :setup_wait
)
set /a WAITED+=1
set /a MOD=WAITED %% 5
if %MOD%==0 echo       still waiting for the backend... %WAITED%s of 60s
if %WAITED% GEQ 60 goto :backend_timeout
goto :slow_poll

:setup_wait
set /a MOD=SETUP_WAITED %% 15
if %MOD%==0 echo       backend is installing its dependencies ^(first run^)... %SETUP_WAITED%s
if %SETUP_WAITED% GEQ 900 goto :backend_timeout
goto :slow_poll

:backend_timeout
echo.
echo  [ERROR] The backend did not become ready.
echo  Look at the "SAWIE backend" window for the reason, fix it, then run frontend.bat again.
goto :fail

:backend_ready
echo  [ok] Backend is running

REM ---- 4. Vite -------------------------------------------------------------
node scripts\probe.mjs %APP_URL%/ SAWIE
if not errorlevel 1 (
  echo  [ok] The frontend is already running. Opening %APP_URL%
  start "" "%APP_URL%"
  timeout /t 5 >nul
  exit /b 0
)
netstat -ano | findstr /R /C:":5173 .*LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo  [ERROR] Port 5173 is already used by another program.
  for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":5173 .*LISTENING"') do echo  Process ID using the port: %%P
  echo  Close that program, then run frontend.bat again.
  goto :fail
)

echo.
echo  App: %APP_URL%   ^(the browser opens automatically^)
echo  Press Ctrl+C to stop the frontend.
echo.
call npm run dev -- --open
if errorlevel 1 (
  echo.
  echo  [ERROR] The frontend stopped with an error. Read the messages above.
  goto :fail
)
exit /b 0

:fail
echo.
echo  See README.md, section "Troubleshooting".
echo.
pause
exit /b 1
