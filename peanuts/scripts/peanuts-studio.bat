@echo off
rem Launch the Windows GUI directly from the checkout.
rem Unlike the old launcher, the CLI packer is NOT a prerequisite for opening
rem Studio. Users can install/check all game-building prerequisites inside it.
setlocal
set "PEANUTS_REPO=%~dp0..\.."
for %%I in ("%PEANUTS_REPO%") do set "PEANUTS_REPO=%%~fI"
set "PY_CMD=py -3.14"
%PY_CMD% -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if errorlevel 1 (
    set "PY_CMD=py -3"
    py -3 -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
    if errorlevel 1 (
        set "PY_CMD=python"
        python -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
        if errorlevel 1 (
            echo [MISSING] Python 3.10+ is required to launch the GUI from source.
            echo Use the standalone PeanutsStudio.exe from GitHub Actions, which does not require a separate Python installation.
            pause
            exit /b 2
        )
    )
)
%PY_CMD% -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo Installing the PySide6 GUI library in the selected Python environment...
    %PY_CMD% -m pip install -r "%~dp0..\desktop\requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Could not install PySide6. Use the standalone PeanutsStudio.exe instead.
        pause
        exit /b 1
    )
)
%PY_CMD% "%~dp0..\desktop\app.py"
exit /b %errorlevel%
