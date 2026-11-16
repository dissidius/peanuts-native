#!/usr/bin/env python3
"""Build GPL-3.0-or-later unoodle.exe on Windows x64 from the pinned ooz sources.

This uses the exact verified two decoder patches and flags of build.sh. It never
downloads proprietary decoder binaries, and does not add the worker to the APK.
Requires MSYS2 UCRT64 g++ and MSYS2 patch; source hashes are checked first.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OOZ = Path(__file__).resolve().parents[2] / "dm" / "third_party" / "ooz"
PINNED = {
    "kraken.cpp": "20c48a30db54efa7681f8c9c674f2a16f081373872d033885a6fdf244b9cff01",
    "stdafx.h": "92b798615ee1ac90ed53a2685fc62dfbe7133d5ba69e567733d8081d420cf701",
}
SOURCE = ("kraken.cpp", "stdafx.h", "unoodle.cpp")
PATCHES = ("ooz-port.patch", "ooz-guards.patch")


def tool(name, prefix):
    # The PATH on Windows CI may contain Strawberry Perl's ancient patch.exe:
    # it crashes on modern patch headers. Prefer MSYS2's own vetted utility.
    root = Path(os.environ.get("PEANUTS_MSYS2_ROOT", "C:/msys64"))
    exe = root / prefix / (name + ".exe")
    if exe.is_file():
        return str(exe)
    return shutil.which(name)


def build(output):
    if sys.platform != "win32":
        raise RuntimeError("This builder is for native Windows only; use build.sh elsewhere")
    cxx, patch = tool("g++", "ucrt64/bin"), tool("patch", "usr/bin")
    if not cxx or not patch:
        raise RuntimeError("MSYS2 UCRT64 g++ and MSYS2 patch are required (install mingw-w64-ucrt-x86_64-gcc and patch)")
    for name, expected in PINNED.items():
        digest = hashlib.sha256((OOZ / name).read_bytes()).hexdigest()
        if digest != expected:
            raise RuntimeError(name + ": pinned source SHA-256 mismatch")
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="unoodle-", dir=output.parent) as tmp:
        work = Path(tmp)
        for name in SOURCE:
            shutil.copyfile(OOZ / name, work / name)
        for name in PATCHES:
            with (OOZ / name).open("rb") as stream:
                proc = subprocess.run([patch, "-s", "-p1", "--no-backup-if-mismatch"],
                                      cwd=work, stdin=stream, capture_output=True)
            if proc.returncode:
                raise RuntimeError(name + ": patch failed: " + proc.stderr.decode(errors="replace"))
        exe = work / "unoodle.exe"
        cmd = [cxx, "-O2", "-g0", "-fno-strict-aliasing", "-fwrapv", "-msse4.1", "-w",
               "-static", "-I", ".", "-o", str(exe), "unoodle.cpp", "kraken.cpp"]
        proc = subprocess.run(cmd, cwd=work, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace")
        if proc.returncode or not exe.is_file():
            raise RuntimeError("g++ failed: " + proc.stdout[-3500:])
        os.replace(exe, output)
    print("unoodle: built " + str(output), flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: build_unoodle_windows.py <output unoodle.exe>")
    try:
        build(sys.argv[1])
    except (OSError, RuntimeError) as exc:
        sys.exit("[RED] " + str(exc))
