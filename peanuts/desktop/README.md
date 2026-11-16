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

**Launch from source:** Double-click `peanuts/scripts/peanuts-studio.bat`. It needs Python 3.10 or newer and installs only the pinned PySide6 GUI dependency if needed. It no longer requires or silently bootstraps the game packer. Install the packer's separate prerequisites from the **Tools & setup** page. Both launch paths use the same existing backend in `peanuts/scripts/peanuts_build.py`.

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

## In-app Windows prerequisites

The **Tools & setup** page is now the starting point for a first installation.
You do **not** need to install the game packer to open the standalone Studio exe.

- **Check tools:** a read-only scan of MSYS2, the exact UCRT64 GCC/CMake/make/zlib/patch toolchain, ADB, the Python/.NET packer and optional Android APK build tools. The scan finishes without launching downloads, asking console questions or running CMake. If an environment exists, a separate bounded verification checks the real shader dependencies; it cannot silently rebuild the packer.
- **Install missing core tools:** explicitly confirm a sequential installation of MSYS2, the UCRT64 packages, Android Platform-Tools (ADB) and Python 3.14/.NET shader packer. The progress is streamed to the activity console; failure stops the sequence so later installers do not run silently.
- **Install** next to each requirement: installs only that dependency after user confirmation. MSYS2, ADB and optional JDK/Android Studio use Windows Package Manager (`winget`); UCRT64 uses MSYS2's `pacman`; the packer uses this repository's micromamba/conda-forge setup, after asking for an existing destination folder.
- **Custom installation paths:** choose an existing MSYS2 root (the folder containing `usr/bin/bash.exe`) or an `adb.exe` on another drive; click **Save paths and recheck**. The importer is prevented from falling back to Clang or an unrelated MinGW compiler when UCRT64 is not ready.
- **Verify packer:** a finite, non-interactive check of the installed Python, native shader tools and .NET translator. It does not create environments or wait for console input. Studio terminates the checker if it exceeds 60 seconds.
- **Run full preflight:** starts the native importer build/tests only after required MSYS2/UCRT64 files and a packer installation have been found. The builder uses the **absolute UCRT64 compiler** and detects an old Clang CMake cache so your machine cannot silently reuse it.

**Android Studio is not the Android SDK.** Studio detects the SDK root from `ANDROID_HOME`, `ANDROID_SDK_ROOT`, Gradle's `local.properties` or the usual Windows location; you can also select a custom SDK root under **Custom installation paths**. The **Install SDK** action installs the exact components required by `android/app/build.gradle`: Android API 36, NDK 28.2.13676358, and Build-Tools 36.0.0 (plus Platform-Tools). It reuses an existing `sdkmanager.bat`; otherwise it downloads Google's pinned command-line tools ZIP, verifies Google's published SHA-256, and unpacks it into the chosen SDK folder. The GUI requires explicit consent to the applicable Android SDK license terms; downloads, licenses and installation are never triggered by **Check tools**. JDK 21 is available as a separate in-app prerequisite. A playable Android APK still needs a real ARM64 packer stage; see the APK builder page.

If `winget` is missing, install/update Microsoft's App Installer first. MSYS2 installation defaults to `C:\msys64`; you can select a nonstandard root in Studio. The installer uses your Windows permissions, so Windows may request elevation. **All installations require explicit confirmation**, and your keys/game dumps never leave the machine.

## Android-inspired modern interface

Studio now adopts the Android app's **cream, warm ivory, cocoa text and golden-yellow accents**, adapted to a spacious Windows layout rather than reproducing narrow phone screens. The dashboard and other views reuse one coherent card/button/metric design system. There are no fabricated game covers or installable games: the library and its state come from the Android app's `status.json` over ADB.

## Pages

- **Dashboard:** actual library totals, Ready and Building counts, phone connection, keys/firmware/GPU readiness, and an active Build/Prepare job if the Android app reports one.
- **Game library:** searchable, filterable three-column game cards. Ready is shown only when Android's actual library state is `ready`; live progress is shown only for its active game. Selecting a card opens that game's desktop ADB management panel.
- **PC builder:** drag/drop NSP, XCI, NUP or dump folder; optional update version, DLC, keys path, destination folder, shader worker count and dry run; ADB transfer when requested; streaming output and cancellation. All operations call the repository's real PC packer.
- **Build center:** native Android Build/Prepare status, actual step text, counted work units and Android-reported ETA, pause/resume/retry, diagnostic and log locations. PC build output remains in the global activity console.
- **Live PC activity:** compact progress bar summarizes real native output (for example, `54,080/73,496 shaders (74%)`); it logs translation milestones instead of thousands of identical lines. Expand **Show logs** to inspect messages, or **Save log** to export the full raw process output for troubleshooting. Changing pages never stops an active build. `status.json` does not provide a PC job queue, so no unrelated fake progress is displayed.
- **Android device:** selected ADB device, keys/firmware/driver, configured game/update/DLC/build folders and free space; send a pack, install an APK without uninstalling another signature, open Android settings, rescan, and pull app logs.
- **Companions:** catalog loaded by Android on request, with searchable cards, actual package versions/installation states, and enabled install/update/remove only for built games. A new optional read-only ADB flag `companion do=list all=true` includes games not in the user's library; older Android APKs that do not implement the flag return only matches for their local games.
- **ADB controls:** real library/status table, on-device Build/Prepare/Play, guarded job commands and known settings (fps, resolution, upscaler, console mode, overlay, screen-on and Switch/DualSense touch skin). **Advanced settings not exposed by the ADB API** (GPU driver management, frame generation, physical controller mapping, motion and game-specific choices) are opened in the Android UI using the existing safe `nav` command, not simulated in Windows.
- **APK builder:** Gradle/NDK build of a development APK only with a validated **real Android ARM64 packer stage**; optional stage generation via a configured WSL2 distribution. No fake playable APK or signing-key harvesting.
- **Tools & setup:** noninteractive prerequisite checks, explicit Windows dependency installations, custom MSYS2/ADB paths and precise compiler preflight. Packages and game data stay local; dependencies come from their designated package managers.


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
