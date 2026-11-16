#!/usr/bin/env python3
"""Explicit, resumable Android SDK component installer for Peanuts Studio (Windows).

Downloads Google's *pinned*, checksum-verified command-line tools only if
sdkmanager is not yet installed, then installs the Android packages pinned by
android/app/build.gradle. The parent GUI obtains an explicit acknowledgement
of the Android SDK licenses before launching this script. It never installs
the Android Studio IDE, firmware, console keys or games.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

CMDLINE_URL = "https://dl.google.com/android/repository/commandlinetools-win-15859902_latest.zip"
CMDLINE_SHA256 = "90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a"
PACKAGES = ("platforms;android-36", "ndk;28.2.13676358", "build-tools;36.0.0", "platform-tools")

def say(line):
    print(line, flush=True)

def sdkmanager(root):
    base = root / "cmdline-tools"
    candidates = [base / "latest/bin/sdkmanager.bat"]
    if base.is_dir():
        candidates += sorted(base.glob("*/bin/sdkmanager.bat"), reverse=True)
    candidates.append(root / "tools/bin/sdkmanager.bat")
    return next((path for path in candidates if path.is_file()), None)

def download_tools(root):
    dest = root / "cmdline-tools/latest"
    if dest.exists():
        raise RuntimeError("Command-line tools are incomplete at " + str(dest) +
                           ". Repair them in Android Studio > SDK Manager rather than deleting existing files.")
    root.mkdir(parents=True, exist_ok=True)
    cache = root / ".peanuts-cmdline-tools.zip.part"
    say("Downloading official Android SDK command-line tools (~156 MB) from Google…")
    sha = hashlib.sha256()
    try:
        with urllib.request.urlopen(urllib.request.Request(CMDLINE_URL, headers={
            "User-Agent": "Peanuts-Studio-SDK-Installer/1.0"}), timeout=40) as response, cache.open("wb") as out:
            total = int(response.headers.get("Content-Length", "0"))
            written = 0
            last = -1
            while True:
                buf = response.read(1024 * 512)
                if not buf: break
                out.write(buf)
                sha.update(buf)
                written += len(buf)
                percent = written * 100 // total if total else 0
                if total and percent // 5 != last:
                    last = percent // 5
                    say("download: " + str(percent) + "%")
        if sha.hexdigest() != CMDLINE_SHA256:
            raise RuntimeError("Google command-line-tools SHA-256 did not match the official checksum. Nothing was installed.")
        stage = root / "cmdline-tools/.peanuts-install"
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True)
        with zipfile.ZipFile(cache) as z:
            for info in z.infolist():
                parts = Path(info.filename).parts
                if not parts or parts[0] != "cmdline-tools" or ".." in parts:
                    raise RuntimeError("Unexpected command-line-tools archive path: " + info.filename)
                relative = Path(*parts[1:])
                if not relative.parts: continue
                target = stage / relative
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(info) as src, target.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
        if not (stage / "bin/sdkmanager.bat").is_file() or not (stage / "source.properties").is_file():
            raise RuntimeError("Official tools archive missing expected SDK Manager contents.")
        stage.rename(dest)
        say("Android SDK command-line tools installed and checksum verified.")
    finally:
        if cache.is_file():
            cache.unlink()

def java_environment():
    env = dict(os.environ)
    if shutil.which("java", path=env.get("PATH")):
        return env
    roots = [
        Path(os.environ.get("JAVA_HOME", "")) if os.environ.get("JAVA_HOME") else None,
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Eclipse Adoptium",
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Java",
    ]
    for root in roots:
        if not root or not root.is_dir(): continue
        dirs = [root] if (root / "bin/java.exe").is_file() else list(root.glob("*"))
        for candidate in dirs:
            if (candidate / "bin/java.exe").is_file():
                env["JAVA_HOME"] = str(candidate)
                env["PATH"] = str(candidate / "bin") + os.pathsep + env.get("PATH", "")
                return env
    raise RuntimeError("Java runtime not found. Install JDK 21 from Studio's Tools & setup page first.")

def run_sdkmanager(manager, root, env, *args, accept=False):
    command = [str(manager), "--sdk_root=" + str(root), *args]
    # Only the explicit GUI's SDK-license consent authorizes answering Google's
    # SDK Manager license prompts, and only for this specific installation.
    proc = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
        bufsize=1, env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if proc.stdin:
        try:
            if accept:
                proc.stdin.write("y\n" * 128)
                proc.stdin.flush()
        except BrokenPipeError:
            pass
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass
    if proc.stdout:
        # SDK Manager uses both CR progress updates and normal LF output.
        # TextIOWrapper's universal-newline handling yields either as a line.
        for line in proc.stdout:
            if line.strip():
                say(line.rstrip())
        proc.stdout.close()
    exit_code = proc.wait()
    if exit_code:
        raise RuntimeError("Android SDK Manager failed (exit " + str(exit_code) + ").")
    return exit_code


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("action", choices=["install"])
    cli.add_argument("--sdk-root", required=True)
    cli.add_argument("--license-consent", action="store_true")
    args = cli.parse_args()
    if not args.license_consent:
        raise RuntimeError("Explicit license consent from the Studio confirmation dialog is required.")
    root = Path(args.sdk_root).expanduser().resolve()
    if os.name != "nt":
        raise RuntimeError("This installer is intended for the Windows Studio application.")
    env = java_environment()
    manager = sdkmanager(root)
    if not manager:
        download_tools(root)
        manager = sdkmanager(root)
    if not manager:
        raise RuntimeError("sdkmanager.bat could not be found after installation.")
    say("SDK destination: " + str(root))
    say("Reviewing/accepting Google Android SDK package licenses as authorized in the Studio dialog…")
    run_sdkmanager(manager, root, env, "--licenses", accept=True)
    say("Installing required Android API 36, NDK 28.2 and Build-Tools 36.0.0…")
    run_sdkmanager(manager, root, env, "--install", *PACKAGES, accept=True)
    expected = [root / "platforms/android-36/android.jar",
                root / "ndk/28.2.13676358/source.properties",
                root / "build-tools/36.0.0/aapt2.exe"]
    missing = [str(p) for p in expected if not p.is_file()]
    if missing:
        raise RuntimeError("SDK Manager returned success but these files are missing: " + ", ".join(missing))
    say("✓ Android SDK API 36, NDK 28.2 and Build-Tools 36.0.0 installed and verified.")

if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as err:
        print("[SDK SETUP ERROR] " + str(err), file=sys.stderr, flush=True)
        sys.exit(1)
