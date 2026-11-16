"""Local, non-interactive Windows prerequisite discovery for Peanuts Studio.

A check never installs software, opens a prompt or calls winget/pacman.
Install commands are explicit user actions; dependencies are verified again
after each command finishes. All paths may be overridden by the user.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

MSYS_PACKAGES = (
    "mingw-w64-ucrt-x86_64-gcc",
    "mingw-w64-ucrt-x86_64-make",
    "mingw-w64-ucrt-x86_64-cmake",
    "mingw-w64-ucrt-x86_64-zlib",
    "patch",
)

def msys_root(custom=""):
    roots = [custom, os.environ.get("PEANUTS_MSYS2_ROOT", ""),
             str(Path(os.environ.get("SystemDrive", "C:")) / "msys64"),
             str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/MSYS2")]
    for candidate in roots:
        if candidate and (Path(candidate) / "usr/bin/bash.exe").is_file():
            return Path(candidate).resolve()
    return Path(custom or roots[2])

def ucrt_bin(custom=""):
    if custom and (Path(custom) / "gcc.exe").is_file():
        return Path(custom).resolve()
    override = os.environ.get("PEANUTS_MSYS2_UCRT64", "")
    if override and (Path(override) / "gcc.exe").is_file():
        return Path(override)
    return msys_root().joinpath("ucrt64", "bin")

def adb_executable(custom=""):
    if custom and Path(custom).is_file():
        return str(Path(custom).resolve())
    explicit = os.environ.get("PEANUTS_ADB", "")
    if explicit and Path(explicit).is_file():
        return str(Path(explicit).resolve())
    found = shutil.which("adb")
    if found:
        return found
    home = Path.home()
    appdata = Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local"))
    options = [
        Path(os.environ.get("ANDROID_HOME", "")) / "platform-tools/adb.exe" if os.environ.get("ANDROID_HOME") else None,
        Path(os.environ.get("ANDROID_SDK_ROOT", "")) / "platform-tools/adb.exe" if os.environ.get("ANDROID_SDK_ROOT") else None,
        appdata / "Android/Sdk/platform-tools/adb.exe",
        home / "platform-tools/adb.exe",
        appdata / "Microsoft/WinGet/Links/adb.exe",
    ]
    for glob in ("Google.PlatformTools_*/platform-tools/adb.exe", "Google.PlatformTools_*/adb.exe"):
        options.extend((appdata / "Microsoft/WinGet/Packages").glob(glob))
    for item in options:
        if item is not None and item.is_file():
            return str(item.resolve())
    return ""

def packer_prefix(repo):
    env = os.environ.get("BANANATIVE_ENV", "")
    record = Path(repo) / ".bananative-env"
    value = env or (record.read_text(encoding="utf-8").strip() if record.is_file() else "")
    return Path(value) if value else None

def packer_state(repo, *, deep=False):
    prefix = packer_prefix(repo)
    py = prefix / "python.exe" if prefix else None
    if py is None or not py.is_file():
        return False, "Not installed. Choose 'Install' to create the Python 3.14/.NET packer environment."
    if not deep:
        return True, "Installed at " + str(prefix) + " (select Verify tools for full checks)"
    try:
        proc = subprocess.run(
            [str(py), str(Path(repo) / "scripts/bananative_env.py"), "--quiet"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace", timeout=25,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if proc.returncode:
            return False, "Environment incomplete: " + (proc.stdout or "verification failed")[-450:]
        return True, "Python 3.14, shader translator and SPIR-V tools verified"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, "Environment verification failed: " + str(exc)

def sdk_root():
    roots = [os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"),
             str(Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "Android/Sdk")]
    for root in roots:
        if root and Path(root, "platforms/android-36/android.jar").is_file():
            return Path(root)
    return Path(roots[-1])

def dependency_status(repo, *, adb="", root="", deep=False):
    """Returns stable tuples: (id, ready, detail, optional).
    Optional Android APK tools are distinguished from core PC game pack tools.
    """
    root = msys_root(root)
    binpath = root / "ucrt64/bin"
    bash = root / "usr/bin/bash.exe"
    gcc = binpath / "gcc.exe"
    required = [gcc, binpath / "g++.exe", binpath / "cmake.exe",
                binpath / "mingw32-make.exe", root / "usr/bin/patch.exe",
                root / "ucrt64/include/zlib.h"]
    zlib = any((root / "ucrt64/lib" / name).is_file()
               for name in ("libz.a", "libz.dll.a", "zlib.lib"))
    missing = [x.name for x in required if not x.is_file()]
    if not zlib: missing.append("zlib library")
    pack_ok, pack_detail = packer_state(repo, deep=deep)
    adb_path = adb_executable(adb)
    java_home = Path(os.environ.get("JAVA_HOME", "")) if os.environ.get("JAVA_HOME") else None
    javac = shutil.which("javac") or (str(java_home / "bin/javac.exe") if java_home and (java_home / "bin/javac.exe").is_file() else "")
    sdk = sdk_root()
    sdk_components = [sdk / "platforms/android-36/android.jar",
                      sdk / "ndk/28.2.13676358/source.properties"]
    return [
        ("msys", bash.is_file(), str(root) if bash.is_file() else "MSYS2 not found (needed for Windows importer and Oodle decoding)", False),
        ("ucrt", not missing, "UCRT64 ready: " + str(binpath) if not missing else "Missing: " + ", ".join(missing), False),
        ("adb", bool(adb_path), adb_path or "ADB missing (Android SDK Platform-Tools)", False),
        ("packer", pack_ok, pack_detail, False),
        ("java", bool(javac), javac or "JDK 21 is needed for Android APK compilation", True),
        ("sdk", all(x.is_file() for x in sdk_components),
         "Android SDK 36 + NDK 28.2: " + str(sdk) if all(x.is_file() for x in sdk_components)
         else "Android Studio SDK Manager must install Android API 36 and NDK 28.2", True),
    ]

def install_command(kind, repo, *, root="", folder=""):
    """Explicit, bounded, non-interactive child process commands for GUI use.

    The GUI always confirms before calling. Installation may ask Windows for
    elevation; that is an OS dialog, not an unanswerable stdin prompt.
    """
    winget = shutil.which("winget")
    if kind in ("msys", "adb", "java", "studio"):
        ids = {"msys": "MSYS2.MSYS2", "adb": "Google.PlatformTools",
               "java": "EclipseAdoptium.Temurin.21.JDK", "studio": "Google.AndroidStudio"}
        if not winget:
            raise RuntimeError("Windows Package Manager (winget) not found. Install or update App Installer, then retry.")
        return [winget, "install", "--id", ids[kind], "--exact", "--source", "winget",
                "--accept-source-agreements", "--accept-package-agreements",
                "--disable-interactivity", "--silent"]
    if kind == "ucrt":
        base = msys_root(root)
        bash = base / "usr/bin/bash.exe"
        if not bash.is_file():
            raise RuntimeError("Install MSYS2 first, then install the UCRT64 toolchain.")
        # MSYS2 package manager is the authoritative source for compiler and zlib.
        # A full distribution update can require a restart, so do not hide errors.
        shell = "pacman --noconfirm --needed -Syu " + " ".join(MSYS_PACKAGES)
        return [str(bash), "-lc", shell]
    if kind == "packer":
        base = Path(folder) if folder else Path.home()
        if not base.is_dir():
            raise RuntimeError("Select an existing folder for the packer environment.")
        return ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-File", str(Path(repo) / "scripts/bananative.ps1"), "setup", str(base.resolve())]
    raise ValueError("Unknown dependency: " + kind)
