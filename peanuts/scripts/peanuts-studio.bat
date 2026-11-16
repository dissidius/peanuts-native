@echo off
rem Start Peanuts Studio from a repository checkout, with the real packer env.
rem The GUI uses the existing scripts and requires the checkout even if launched from a standalone .exe.
setlocal
set "PEANUTS_REPO=%~dp0..\.."
for %%I in ("%PEANUTS_REPO%") do set "PEANUTS_REPO=%%~fI"
rem The first call installs or recovers the Python 3.14 builder environment.
call "%~dp0..\..\scripts\bananative.bat" check
if errorlevel 1 (
  echo [RED] Peanuts packer setup failed. See the message above.
  pause
  exit /b 1
)
if not exist "%PEANUTS_REPO%\.bananative-env" (
  echo [RED] Missing packer environment record.
  pause
  exit /b 1
)
set /p "PACK_ENV="<"%PEANUTS_REPO%\.bananative-env"
if not exist "%PACK_ENV%\python.exe" (
  echo [RED] Packer Python not found in "%PACK_ENV%"
  pause
  exit /b 1
)
"%PACK_ENV%\python.exe" -c "import PySide6" >nul 2>&1
if errorlevel 1 (
  echo Installing Qt for Peanuts Studio into the local packer environment...
  "%PACK_ENV%\python.exe" -m pip install -r "%~dp0..\desktop\requirements.txt"
  if errorlevel 1 (
    echo [RED] Failed to install the desktop UI dependency.
    pause
    exit /b 1
  )
)
"%PACK_ENV%\python.exe" "%~dp0..\desktop\app.py"
exit /b %errorlevel%
