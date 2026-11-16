"""Non-UI command planner for Peanuts Studio, the Windows-to-Android desktop front-end.

The source game data and console keys remain local. We never upload them or
embed them in GitHub Actions. All shell-exposed args are separate argv entries.
"""
import os
import re
import sys
from pathlib import Path

import dependencies as deps

PACKAGE = "dev.nxnative.android.peanuts"
CONTROL = PACKAGE + "/dev.peanuts.ctl.Command"
STATUS = "/sdcard/Android/data/" + PACKAGE + "/files/ctl/status.json"
DEST = "/sdcard/Peanut Roms"
TITLE = re.compile(r"^[0-9A-Fa-f]{16}$")


def repo_root():
    env = os.environ.get("PEANUTS_REPO")
    candidates = ([Path(env)] if env else []) + [
        Path.cwd(), Path(__file__).resolve(), Path(sys.executable).parent
    ]
    for base in candidates:
        for folder in [base, *base.parents]:
            if (folder / "peanuts/scripts/peanuts_build.py").is_file():
                return folder.resolve()
    raise FileNotFoundError("Open Peanuts Studio from its source checkout, or set PEANUTS_REPO to the repository directory.")


def tool_python(repo):
    override = os.environ.get("BANANATIVE_ENV")
    config = repo / ".bananative-env"
    path = override or (config.read_text(encoding="utf-8").strip() if config.is_file() else "")
    if path:
        py = Path(path) / ("python.exe" if os.name == "nt" else "bin/python")
        if py.is_file():
            return str(py)
    raise RuntimeError("Packer environment not installed. Run scripts\\bananative.bat setup once, then reopen the Studio.")


def builder_environment(repo):
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    candidates = []
    if os.name == "nt":
        root = deps.msys_root()
        candidates += [root / "ucrt64/bin", root / "usr/bin"]
    config = repo / ".bananative-env"
    prefix = env.get("BANANATIVE_ENV") or (config.read_text(encoding="utf-8").strip() if config.is_file() else "")
    if prefix:
        p = Path(prefix)
        candidates += [p, p / "Library/bin", p / "Scripts"]
        for dn in (p / "dotnet", p / "Library/dotnet"):
            if (dn / "dotnet.exe").is_file() and not env.get("DOTNET_ROOT"):
                env["DOTNET_ROOT"] = str(dn)
                break
    env["PATH"] = os.pathsep.join([str(p) for p in candidates if p.is_dir()] + [env.get("PATH", "")])
    return env


def game_command(repo, python, inputs, *, keys="", update="", out="", threads=8,
                 push=False, serial="", dest="", force=False, any_version=False,
                 no_shaders=False, dry=False):
    sources = [str(Path(x).resolve()) for x in inputs if str(x).strip()]
    if not sources or not all(Path(x).exists() for x in sources):
        raise ValueError("Select at least one existing NSP, XCI, NUP or dump folder.")
    # NUP and dump folders must be alone; the underlying builder checks consistency.
    cmd = [python, "-u", str(repo / "peanuts/scripts/peanuts_build.py"), *sources]
    if keys:
        if not Path(keys).is_file():
            raise ValueError("Selected keys file does not exist.")
        cmd += ["--keys", str(Path(keys).resolve())]
    if update:
        if not update.isdigit(): raise ValueError("Update must be a numeric version, such as 131072.")
        cmd += ["--update", update]
    if out: cmd += ["--nup", str(Path(out).resolve())]
    if force: cmd.append("--force-nup")
    if any_version: cmd.append("--any-version")
    if dry: cmd.append("--dry-run")
    if push:
        if not serial: raise ValueError("Choose a connected and authorized Android device for ADB push.")
        cmd += ["--push", "--serial", serial]
        if dest: cmd += ["--dest", dest]
    extras = ["-J", str(max(1, min(int(threads), 128)))]
    if no_shaders: extras.append("--no-shaders")
    cmd += ["--", *extras]
    return cmd


def adb_command(serial, args):
    if not serial or re.search(r"\s", serial):
        raise ValueError("Select an authorized ADB device.")
    return [deps.adb_executable() or "adb", "-s", serial, *args]


def control_command(serial, command, fields=None, request_id=None):
    if not re.fullmatch(r"[a-z_]+", command):
        raise ValueError("Invalid control command.")
    args = ["shell", "am", "start", "-n", CONTROL, "-e", "cmd", command]
    for key, value in (fields or {}).items():
        if not re.fullmatch(r"[a-z_]+", key): raise ValueError("Invalid control argument.")
        args += ["-e", key, str(value)]
    if request_id: args += ["-e", "id", request_id]
    return adb_command(serial, args)


def gradle_command(repo, stage, games, extra=None):
    stage = Path(stage)
    required = ["lib/libpython3.14.so", "lib/libnxpack.so", "lib/libzbicdec.so",
                "lib/libdmsh_xlate.so", "lib/libSPIRV-Tools-shared.so",
                "python/lib/python3.14/os.py"]
    missing = [str(stage / x) for x in required if not (stage / x).is_file()]
    if missing:
        raise ValueError("An Android ARM64 packer stage is required (build it on Linux/WSL first). Missing: " + missing[0])
    title_ids = [s.strip().upper() for s in games.split(",") if s.strip()]
    if title_ids and (not all(TITLE.fullmatch(s) for s in title_ids)
                      or any(not (repo / "dm/games" / s / "game.tsv").is_file() for s in title_ids)):
        raise ValueError("Game IDs must be 16-digit hex values with a profile under dm/games.")
    gradle = repo / "android/app/gradlew.bat"
    if not gradle.is_file(): raise FileNotFoundError("Android Gradle wrapper not found.")
    cmd = ["cmd.exe", "/d", "/c", str(gradle), "--project-dir", str(repo / "android/app"), "-PnxApp=peanuts",
           "-PnxGenericHost=true", "-PnxPackStage=" + str(stage.resolve())]
    if title_ids: cmd.append("-PnxGames=" + ",".join(title_ids))
    cmd += list(extra or []) + ["apk"]
    return cmd


def status_command(serial):
    return adb_command(serial, ["shell", "cat", STATUS])


def wsl_stage_command(repo, work):
    """Prepare the *real* Android ARM64 stage through configured WSL2 Linux.

    The existing Linux/zsh build compiles Android CPython, NativeAOT translator
    and SPIR-V Tools using the Android NDK. It requires zsh, Linux .NET 10 SDK,
    ANDROID_NDK_HOME, cmake/ninja, network, and a working WSL2 distribution.
    """
    if os.name != "nt":
        raise RuntimeError("WSL stage generation is available on Windows only.")
    import shlex
    work = Path(work).expanduser().resolve()
    if not work.is_dir():
        raise ValueError("Create/select an existing Windows work folder for the stage.")
    def quote(p):
        return shlex.quote(str(p))
    script = (
        "set -e; "
        + "r=$(wslpath -a -u " + quote(repo) + "); "
        + "w=$(wslpath -a -u " + quote(work) + "); "
        + "test -d \"$r/android/ondevice\"; "
        + "test -n \"$ANDROID_NDK_HOME\" || { echo 'ANDROID_NDK_HOME is not set inside WSL'; exit 1; }; "
        + "cd \"$r\"; zsh peanuts/scripts/ondevice-stage.sh \"$w\" all"
    )
    return ["wsl.exe", "--exec", "bash", "-lc", script]
