# Windows runtime port — architecture and implementation gates

Status: **design / not playable**. This is a Windows *execution* target, not the existing Windows pack builder. No Windows game-running executable has been produced or validated.

## Scope

- Target first: Windows 11 ARM64 with Vulkan 1.3, using the existing rewritten ARM64 guest and the existing Vulkan NVN replay.
- Target second: Windows 11 x64. Original Switch ARM64 game code cannot execute directly on x86-64 CPUs. A verified ARM64-to-x64 ahead-of-time recompiler or dynamic translator is required; recompiling only the host is not enough.
- Preserve the Android app, game profiles, packaging format, and Peanuts companion runtime. Do not change Android behavior to work around Windows dependencies.

## Existing building blocks

- `dm/host/`: Horizon services, module loading and guest bootstrap (primarily POSIX).
- `dm/host/plat/plat.h`: currently rejects non-Apple/non-Android hosts at preprocessing time; its memory mapping, guest TLS slots, thread contexts, timing, unwind/signals and other APIs must receive Windows implementations.
- `android/host/CMakeLists.txt`: currently rejects every non-Android ARM64 target and includes Android-only front, input, media and platform sources.
- `dm/gfx/vk_android/`: the existing NVN → Vulkan replay; audit Android surface, loader, presentation, synchronization and graphics-driver imports before extracting a platform-neutral Vulkan core.
- `dm/peanuts/rt/`: companion runtime; audit platform assumptions and select a Windows UI host.
- `peanuts/scripts/peanuts-build.bat`: existing Windows **packing tool**, not a Windows runtime.

## Milestones and acceptance criteria

### 1. Windows ARM64 platform host

- Add `PLAT_WINDOWS` and a separate `plat_windows.c` implementing `plat.h` with documented Win32/NT mappings.
- Map guest module address space with correct reservation and permission transitions; add tests for relocations, memory aliases and guest read/write.
- Implement ARM64 guest thread state, TLS slot mapping, context transitions, exception/SEH handling, clock, filesystem and process setup.
- Keep platform entry points separate from Android JNI and Apple Cocoa.
- Gate: native ARM64 host test suite builds and passes on a Windows ARM64 runner/device; guest bootstrap reaches a traced entry point.

### 2. Platform-neutral Vulkan replay

- Extract Vulkan core from Android-only surface creation, Android hardware buffer, JNI and Android driver-loader paths.
- Add Win32 `VkSurfaceKHR`, swapchain/window, presentation pacing and standard Vulkan loader selection.
- Add Win32 input, XInput/SDL or GameInput controller support, audio backend, and video decoding strategy.
- Gate: rendering validation and a frame capture on a real Windows ARM64 Vulkan driver.

### 3. Executable pack and frontend

- Consume the existing game profile/pack output; implement launcher, per-game environment, user storage, logs and saves.
- Port optional companions to a desktop side-panel, not an assumed second Android display.
- Add Windows CI with explicit ARM64 runtime smoke tests. Do not publish gameplay claims without end-to-end device testing.
- Gate: launch one verified title from a legally obtained local dump, save/load, controller input, audio and Vulkan rendering.

### 4. Windows x64 guest code strategy (separate project gate)

- Audit `dm/tools/patch_nso.py` and its rewrite outputs before selecting an ARM64→x64 compiler/translator.
- Define x64 guest calling ABI, TLS and exception transitions, SVC and HLE thunk conventions, SIMD and memory ordering, code/data relocation and dynamically loaded NSOs.
- Implement/validate the translator independently of Vulkan; test guest execution and service calls before graphics bring-up.
- Gate: an x64 build runs a guest ARM64 instruction/service test corpus and then a supported game's main loop.

## Do not confuse

- The existing `.bat` builder prepares **Android** game packs on Windows.
- Windows ARM64 runs native ARM64 code, but Android/Linux ELF guest modules still require the host rewrite, loader and services.
- Windows x64 requires guest-code translation/recompilation even when the host and Vulkan layer compile.
- Neither running the Android APK under a subsystem nor building the host library alone constitutes this port.

## Near-term engineering order

1. Introduce a Windows-only CI compile/test target for portable host components, without claiming playability.
2. Refactor `plat.h` architecture-specific assumptions behind a stable per-platform interface.
3. Bootstrap an ARM64 Win32 host and integrate the Vulkan Win32 surface.
4. Only then evaluate x64 AOT/recompilation; no blind substitution of a generic ARM emulator.
