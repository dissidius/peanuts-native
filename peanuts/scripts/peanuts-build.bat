@echo off
rem Peanuts Native's builder on Windows: .nsp / .xci (or a .nup, or a dump folder) -> .nup -> pack -> (with --push) Android.
rem Use the MSYS2 UCRT64 compiler and zlib automatically when installed in the default MSYS2 location.
rem Run peanuts\scripts\windows-builder-check.ps1 once to validate the toolchain without needing game files.
setlocal
if exist "%SystemDrive%\msys64\ucrt64\bin\gcc.exe" set "PATH=%SystemDrive%\msys64\ucrt64\bin;%SystemDrive%\msys64\usr\bin;%PATH%"
call "%~dp0..\..\scripts\bananative.bat" python "%~dp0peanuts_build.py" %*
exit /b %errorlevel%
