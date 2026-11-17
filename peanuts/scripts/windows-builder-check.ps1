# Windows PC preflight: no game files or prod.keys required.
# This check NEVER installs dependencies. Use the Studio Tools page installers first.
param([switch]$SkipPackerEnvironment)
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Root = if ($env:PEANUTS_MSYS2_ROOT) { $env:PEANUTS_MSYS2_ROOT } else { Join-Path "$env:SystemDrive\" 'msys64' }
$Ucrt = if ($env:PEANUTS_MSYS2_UCRT64) { $env:PEANUTS_MSYS2_UCRT64 } else { Join-Path $Root 'ucrt64\bin' }
$Gcc = Join-Path $Ucrt 'gcc.exe'
$Make = Join-Path $Ucrt 'mingw32-make.exe'
$Cmake = Join-Path $Ucrt 'cmake.exe'
$Ctest = Join-Path $Ucrt 'ctest.exe'
$ZlibHeader = Join-Path $Root 'ucrt64\include\zlib.h'
$ZlibLib = @((Join-Path $Root 'ucrt64\lib\libz.a'), (Join-Path $Root 'ucrt64\lib\libz.dll.a'))
$Patch = Join-Path $Root 'usr\bin\patch.exe'
$Missing = @()
foreach ($entry in @($Gcc, $Make, $Cmake, $Ctest, $ZlibHeader, $Patch)) {
    if (!(Test-Path -PathType Leaf $entry)) { $Missing += $entry }
}
if (-not ($ZlibLib | Where-Object { Test-Path -PathType Leaf $_ })) {
    $Missing += 'UCRT64 zlib library (libz.a/libz.dll.a)'
}
if ($Missing.Count) {
    Write-Host '[MISSING] MSYS2 UCRT64 toolchain is incomplete. Windows compiler fallback is disabled.' -ForegroundColor Yellow
    $Missing | ForEach-Object { Write-Host ('  - ' + $_) }
    Write-Host 'In Peanuts Studio open Tools & setup and install MSYS2, then UCRT64 toolchain.'
    exit 2
}
$env:PATH = "$Ucrt;$(Join-Path $Root 'usr\bin');$env:PATH"
$Build = Join-Path $Repo 'peanuts\.build\nximport'
# A stale CMake cache from Clang or another toolchain must not persist.
$Cache = Join-Path $Build 'CMakeCache.txt'
if (Test-Path $Cache) {
    $value = Get-Content $Cache | Where-Object { $_ -like 'CMAKE_C_COMPILER:FILEPATH=*' } | Select-Object -First 1
    $want = ($Gcc -replace '\\', '/')
    if (-not $value -or -not ($value -replace '\\', '/').EndsWith($want)) {
        Write-Host '[INFO] Clearing stale CMake cache (different compiler).'
        Remove-Item -LiteralPath $Cache -Force
        $CmakeFiles = Join-Path $Build 'CMakeFiles'
        if (Test-Path $CmakeFiles) { Remove-Item -LiteralPath $CmakeFiles -Recurse -Force }
    }
}
Write-Host '[1/4] Compile native importer using MSYS2 UCRT64 GCC' -ForegroundColor Cyan
$ArgsList = @('-S', (Join-Path $Repo 'dm\peanuts\import'), '-B', $Build, '-G', 'MinGW Makefiles',
    "-DCMAKE_C_COMPILER=$Gcc", "-DCMAKE_MAKE_PROGRAM=$Make",
    "-DCMAKE_PREFIX_PATH=$(Join-Path $Root 'ucrt64')", '-DCMAKE_BUILD_TYPE=Release')
& $Cmake @ArgsList
if ($LASTEXITCODE -ne 0) { throw 'Importer CMake configuration failed.' }
& $Cmake --build $Build --parallel 4
if ($LASTEXITCODE -ne 0) { throw 'Importer build failed.' }
Write-Host '[2/4] Run synthetic native importer tests' -ForegroundColor Cyan
& $Ctest --test-dir $Build --output-on-failure
if ($LASTEXITCODE -ne 0) { throw 'Native importer tests failed.' }
Write-Host '[3/4] Run Windows builder Python tests' -ForegroundColor Cyan
$TestScript = Join-Path $Repo 'peanuts\tests\test_peanuts_build.py'
if ($SkipPackerEnvironment) {
    $Py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $Py) { throw 'CI Python 3.14 is missing.' }
    & $Py.Source $TestScript
} else {
    & (Join-Path $Repo 'scripts\bananative.bat') check
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Packer missing/incomplete. Use Studio > Tools & setup > Install packer environment.'
        exit 2
    }
    & (Join-Path $Repo 'scripts\bananative.bat') python $TestScript
}
if ($LASTEXITCODE -ne 0) { throw 'Python builder tests failed.' }
Write-Host '[4/4] Tools check completed (no packages installed).' -ForegroundColor Cyan
Write-Host 'Windows preflight passed. Actual Android gameplay still requires game/device testing.' -ForegroundColor Green
