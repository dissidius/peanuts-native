# Peanuts Studio — Windows PC → Android GUI

Peanuts Studio is a **Windows desktop front-end** for the existing Peanuts
Native game packer and Android app. The target runtime is still **Android
ARM64**: the PC does the costly import, code rewrite and Vulkan shader
translation, then transfers the result to the phone.

## Launch

**Prebuilt desktop executable:** Open the `Peanuts Studio Windows GUI` GitHub
Actions run, download the `PeanutsStudio-Windows-x64` artifact and extract the
`PeanutsStudio.exe` into the root of a checkout of this repository. Double-click
it. Or set `PEANUTS_REPO` to an existing checkout before launching the exe.

**Launch from source:** Double-click
`peanuts/scripts/peanuts-studio.bat`. It bootstraps/reuses the repository's
existing Python 3.14 packer environment and installs the pinned PySide6 GUI
dependency there on first use. Both launch paths use the **same** existing
backend in `peanuts/scripts/peanuts_build.py`.

For the Windows importer install [MSYS2 UCRT64](https://www.msys2.org/) into
`C:\msys64`. In an **MSYS2 UCRT64** shell:

```sh
pacman -Syu
pacman -S --needed mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-make mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-zlib patch
```

If MSYS2 updates ask for shell restart, do that before installing packages.
The PC packer environment is installed using the **Tools & setup** page or
`scripts/bananative.bat setup`. Install Android
[platform-tools](https://developer.android.com/tools/releases/platform-tools)
and make `adb devices` show one authorized device before transfers.

## Pages

- **Overview:** guided path, last known Android state, local conversion limits.
- **Game builder:** drag/drop NSP, XCI, NUP or dump folder; optional update
  version, DLC, keys path, destination folder, shader workers, dry run;
  optional ADB push after preparation; streamed log, progress and cancellation.
- **Android device:** discover authorized ADB devices; transfer an existing
  pack and game to the phone; rescan; install an existing APK; pull app logs.
- **ADB control:** reads the Android app's real `ctl/status.json` and library.
  Operates the **existing** guarded Android control activity for scan, build,
  prepare, pause, resume, retry, play, game stop, select settings and companion
  list/install/update/remove. It does not bypass the app's checks. Removing a
  companion or stopping a game asks for confirmation.
- **APK builder:** invokes the existing Gradle + Android NDK build for an
  installable **test** APK when the **real Android ARM64 packer stage already
  exists**. The **Generate stage via WSL2** button runs the repository's
  Linux stage builder in a configured WSL2 distribution; it requires the Linux
  .NET 10 SDK, zsh, Android NDK and `ANDROID_NDK_HOME` inside WSL, and a
  Windows work folder. There is no native Windows stage builder yet. No
  simulated or fake packer stage is offered as an equivalent.
- **Tools & setup:** checks/installs local tool dependencies and opens outputs.

The GUI neither stores the console keys contents nor commits or uploads game
files. The `prod.keys` path is passed only to the local importer when it is
needed; saved logs should still be reviewed before sharing.

## Oodle and Unreal decoding on Windows x64

The PC packer uses the independent open-source **unoodle.exe** program, built
locally from the pinned, GPL-3.0-or-later Oodle decoder sources. The executable
uses Win32 protected guard pages and **binary stdin/stdout** for the existing
pipe protocol. It remains separate from Peanuts Studio and the Android APK.
Encrypted Unreal pak indexes use PyCryptodome through the private
`_nxaes` compatibility adapter on Windows.

The repository has strict shader-key validation for four specific profiles:
Pokémon Legends: Arceus, FINAL FANTASY RESONANCE, OCTOPATH TRAVELER 0 and
DRAGON QUEST III HD-2D Remake. **Do not assume every game that uses Oodle or
Unreal is supported.** Unrecognized decoder variants, missing shader keys and
unsupported code paths must fail rather than silently yield a 'ready' game.

The Windows decoder is checked in CI with **synthetic protocol fixtures**.
An end-to-end comparison against a phone-built shader package using actual
game dumps still requires device-specific testing.

## Important Android-specific limitations

This desktop app does not become a Nintendo Switch emulator or Windows game
runtime. It cannot replace a game-specific shader-capture step that genuinely
needs to run the game on Android. For those profiles, use the Android app's
**Build** or **Prepare** action from the ADB control page, and check
`job.state` in the status panel. The control activity cannot set up keys or
firmware, install special GPU drivers, or silently remove saves. See
[`peanuts/docs/CONTROL.md`](../docs/CONTROL.md).

For full pack-builder usage see [`BUILDER.md`](../docs/BUILDER.md). For the
APK's native stage and NDK specifics see [`android/ONDEVICE.md`](../../android/ONDEVICE.md).

## CI verification

`.github/workflows/peanuts-studio-windows.yml` creates the Windows
`PeanutsStudio.exe` artifact, runs no-game command-planner tests, starts the
offscreen Qt GUI from source, and smoke-tests the bundled executable.

`.github/workflows/windows-android-builder.yml` compiles the Windows game
importer, exercises native tests and the Oodle worker, and checks the Windows
packer environment and Unreal AES dependency. **Neither workflow contains
copyrighted games or console keys.**

## Privacy and safeguards

- No network account, telemetry, or cloud library for the Studio.
- No raw shell command box for the Android control activity.
- ADB commands use argument arrays, not formatted commands interpreted by
  a shell, except the project's existing fixed Gradle/Windows batch launchers.
- `adb install -r` never automatically uninstalls a version signed with a
  different key. Keep the release install and saves intact.
- Avoid pressing Stop on a device job that has unsaved work; check device
  state before invoking play or reimport.
