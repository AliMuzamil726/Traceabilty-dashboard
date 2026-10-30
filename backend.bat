@echo off
REM ==========================================================================
REM  SAWIE backend launcher (Windows 10/11). Double-click to run.
REM  1. find Python 3.11+   2. create backend\venv if missing   3. activate it
REM  4. install requirements only when requirements.txt changed
REM  5. create backend\.env from .env.example   6. start Uvicorn on 127.0.0.1:8000
REM ==========================================================================
setlocal EnableExtensions
title SAWIE backend
cd /d "%~dp0"

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "VENV=%BACKEND%\venv"
set "VPY=%VENV%\Scripts\python.exe"
set "REQ=%ROOT%requirements.txt"
set "MARKER=%VENV%\.req_hash"
set "SETUP_FLAG=%BACKEND%\.setup_in_progress"
set "PORT=8000"
set "HOST=127.0.0.1"

echo.
echo  SAWIE backend
echo  -------------
echo.

REM ---- 1. Python 3.11 or newer ---------------------------------------------
set "PY="
for %%V in (3.13 3.12 3.11) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY (
  py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo  [ERROR] Python 3.11 or newer was not found.
  echo.
  echo  Install it from https://www.python.org/downloads/windows/
  echo  During setup tick "Add python.exe to PATH", then double-click backend.bat again.
  goto :fail
)
for /f "delims=" %%I in ('%PY% -c "import platform; print(platform.python_version())"') do set "PYVER=%%I"
echo  [ok] Python %PYVER%  ^(%PY%^)

REM ---- Port check (before any slow work) -----------------------------------
call :port_in_use
if not errorlevel 1 (
  "%VPY%" -c "import urllib.request,sys; urllib.request.urlopen('http://%HOST%:%PORT%/api/health', timeout=2); sys.exit(0)" >nul 2>&1
  if not errorlevel 1 (
    echo  [ok] The SAWIE backend is already running at http://%HOST%:%PORT%
    echo       API docs: http://%HOST%:%PORT%/docs
    echo.
    echo  Nothing to do. This window closes in 10 seconds.
    timeout /t 10 >nul
    exit /b 0
  )
  %PY% -c "import urllib.request,sys; urllib.request.urlopen('http://%HOST%:%PORT%/api/health', timeout=2); sys.exit(0)" >nul 2>&1
  if not errorlevel 1 (
    echo  [ok] The SAWIE backend is already running at http://%HOST%:%PORT%
    timeout /t 10 >nul
    exit /b 0
  )
  echo  [ERROR] Port %PORT% is already used by another program.
  echo.
  for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    echo  Process ID using the port: %%P
    for /f "tokens=1" %%N in ('tasklist /FI "PID eq %%P" /NH 2^>nul') do echo  Program: %%N
  )
  echo.
  echo  Close that program ^(or end it in Task Manager^), then run backend.bat again.
  goto :fail
)

REM ---- 2. Virtual environment ---------------------------------------------
if exist "%VPY%" (
  "%VPY%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
  if errorlevel 1 (
    echo  [..] The existing virtual environment is broken or too old. Recreating it.
    rmdir /s /q "%VENV%"
  )
)
if not exist "%VPY%" (
  echo  [..] Creating virtual environment in backend\venv
  echo setup> "%SETUP_FLAG%"
  %PY% -m venv "%VENV%"
  if errorlevel 1 (
    echo  [ERROR] Could not create the virtual environment.
    goto :fail_setup
  )
)

REM ---- 3. Activate --------------------------------------------------------
call "%VENV%\Scripts\activate.bat"
if errorlevel 1 (
  echo  [ERROR] Could not activate backend\venv. Delete the folder and try again.
  goto :fail_setup
)
echo  [ok] Virtual environment active

REM ---- 4. Dependencies (only when requirements.txt changed) ---------------
if not exist "%REQ%" (
  echo  [ERROR] requirements.txt is missing next to backend.bat.
  goto :fail_setup
)
for /f "delims=" %%H in ('call "%VPY%" -c "import hashlib; print(hashlib.sha256(open(r'%REQ%','rb').read()).hexdigest())"') do set "NEWHASH=%%H"
set "OLDHASH="
if exist "%MARKER%" set /p OLDHASH=<"%MARKER%"
if /i "%NEWHASH%"=="%OLDHASH%" (
  echo  [ok] Dependencies up to date
) else (
  echo setup> "%SETUP_FLAG%"
  echo  [..] Installing dependencies. The first run takes a few minutes.
  "%VPY%" -m pip install --disable-pip-version-check --upgrade pip
  "%VPY%" -m pip install --disable-pip-version-check -r "%REQ%"
  if errorlevel 1 (
    echo.
    echo  [ERROR] Installing dependencies failed. Check the internet connection and
    echo          the messages above, then run backend.bat again.
    goto :fail_setup
  )
  > "%MARKER%" echo %NEWHASH%
  echo  [ok] Dependencies installed
)
if exist "%SETUP_FLAG%" del /q "%SETUP_FLAG%" >nul 2>&1

REM ---- 5. Configuration ---------------------------------------------------
if not exist "%BACKEND%\.env" (
  copy /y "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
  echo  [ok] Created backend\.env from .env.example
) else (
  echo  [ok] Using backend\.env
)

REM ---- 6. Start Uvicorn ---------------------------------------------------
echo.
echo  API:      http://%HOST%:%PORT%
echo  API docs: http://%HOST%:%PORT%/docs
echo  Health:   http://%HOST%:%PORT%/api/health
echo  Press Ctrl+C to stop the server.
echo.
cd /d "%BACKEND%"
"%VPY%" -m uvicorn app.main:app --host %HOST% --port %PORT% --reload ^
  --reload-dir app --reload-dir core --reload-dir shared --reload-dir scripts ^
  --reload-dir module_1 --reload-dir module_2 --reload-dir module_3 --reload-dir module_4 ^
  --reload-dir module_5 --reload-dir module_6 --reload-dir module_7 --reload-dir module_8 ^
  --reload-dir module_9
if errorlevel 1 (
  echo.
  echo  [ERROR] The backend stopped with an error. Read the messages above.
  goto :fail
)
echo.
echo  The backend has stopped.
pause
exit /b 0

REM ---- helpers ------------------------------------------------------------
:port_in_use
REM errorlevel 0 when something listens on PORT
netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul 2>&1
exit /b %errorlevel%

:fail_setup
if exist "%SETUP_FLAG%" del /q "%SETUP_FLAG%" >nul 2>&1
:fail
echo.
echo  See README.md, section "Troubleshooting".
echo.
pause
exit /b 1
