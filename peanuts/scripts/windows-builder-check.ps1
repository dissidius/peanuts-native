# Run on Windows PowerShell: powershell -NoProfile -ExecutionPolicy Bypass -File peanuts\scripts\windows-builder-check.ps1
# Builds and tests the PC importer using synthetic fixtures. No game dump or prod.keys are needed.
param([switch]$SkipPackerEnvironment)
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Ucrt = Join-Path $env:SystemDrive 'msys64\ucrt64\bin'
if (Test-Path (Join-Path $Ucrt 'gcc.exe')) {
    $env:PATH = "$Ucrt;$env:PATH"
}
function Need([string]$name, [string]$hint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { throw "$name not found. $hint" }
}
Need cmake 'Install MSYS2 UCRT64 CMake (mingw-w64-ucrt-x86_64-cmake).'
Need gcc 'Install the MSYS2 UCRT64 gcc package (mingw-w64-ucrt-x86_64-gcc).'
Need mingw32-make 'Install the MSYS2 UCRT64 make package (mingw-w64-ucrt-x86_64-make).'
Need python 'Install Python 3 and add it to PATH (or let the packer bootstrap its own Python).'
$Build = Join-Path $Repo 'peanuts\.build\nximport'
Write-Host '[1/4] Compile the Windows importer' -ForegroundColor Cyan
& cmake -S (Join-Path $Repo 'dm\peanuts\import') -B $Build -G 'MinGW Makefiles' -DCMAKE_BUILD_TYPE=Release
if ($LASTEXITCODE -ne 0) { throw 'Importer CMake configuration failed.' }
& cmake --build $Build --parallel 4
if ($LASTEXITCODE -ne 0) { throw 'Importer build failed.' }
Write-Host '[2/4] Run native importer tests (synthetic inputs)' -ForegroundColor Cyan
& ctest --test-dir $Build --output-on-failure
if ($LASTEXITCODE -ne 0) { throw 'Native importer tests failed.' }
Write-Host '[3/4] Run Windows builder Python tests' -ForegroundColor Cyan
& python (Join-Path $Repo 'peanuts\tests\test_peanuts_build.py')
if ($LASTEXITCODE -ne 0) { throw 'Python builder tests failed.' }
if (-not $SkipPackerEnvironment) {
    Write-Host '[4/4] Check Windows packer environment' -ForegroundColor Cyan
    & (Join-Path $Repo 'scripts\bananative.bat') check
    if ($LASTEXITCODE -ne 0) { throw 'Packer environment check failed.' }
} else {
    Write-Host '[4/4] Packer environment check skipped (native importer smoke test only).' -ForegroundColor Yellow
}
Write-Host 'Windows builder preflight passed. This does not prove a game pack boots on Android.' -ForegroundColor Green
