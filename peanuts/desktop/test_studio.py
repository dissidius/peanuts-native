#!/usr/bin/env python3
"""No-game smoke tests for Peanuts Studio's command planner and Qt widgets."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import core


class Planner(unittest.TestCase):
    def test_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            nup = Path(tmp) / "Game [01006BB00C6F0000][v0].nup"
            nup.write_bytes(b"synthetic")
            cmd = core.game_command(Path(tmp), "C:/python.exe", [nup],
                                    threads=6, push=True, serial="device-1",
                                    dest="/sdcard/Peanut Roms/Test")
            self.assertIn("--push", cmd)
            self.assertIn("--serial", cmd)
            self.assertEqual(cmd[-3:], ["--", "-J", "6"])
            self.assertNotIn("--keys", cmd)

    def test_missing_file_and_invalid_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            nup = Path(tmp) / "game.nup"
            with self.assertRaises(ValueError): core.game_command(Path(tmp), "python", [nup])
            nup.write_bytes(b"x")
            with self.assertRaises(ValueError):
                core.game_command(Path(tmp), "python", [nup], update="not-a-version")
            with self.assertRaises(ValueError):
                core.game_command(Path(tmp), "python", [nup], push=True)
            with self.assertRaises(ValueError):
                core.game_command(Path(tmp), "python", [nup], keys="missing.keys")

    def test_adb_argv(self):
        cmd = core.control_command("serial-A", "prepare", {"title_id":"01006BB00C6F0000"}, "abc123")
        self.assertIn(Path(cmd[0]).name.lower(), ("adb", "adb.exe"))
        self.assertEqual(cmd[1:4], ["-s", "serial-A", "shell"])
        self.assertIn("dev.nxnative.android.peanuts/dev.peanuts.ctl.Command", cmd)
        self.assertIn("abc123", cmd)
        with self.assertRaises(ValueError):
            core.control_command("abc 1", "status")
        with self.assertRaises(ValueError):
            core.control_command("abc", "status;rm")
        with self.assertRaises(ValueError):
            core.control_command("abc", "status", {"bad;key":"a"})

    @unittest.skipUnless(sys.platform == "win32", "Windows batch and PowerShell only")
    def test_packer_check_missing_ends_without_prompt(self):
        """Check tools must exit instead of blocking on Read-Host on a fresh checkout."""
        import subprocess
        repo = Path(__file__).resolve().parents[2]
        if (repo / ".bananative-env").is_file() or os.environ.get("BANANATIVE_ENV"):
            self.skipTest("Developer already configured a packer environment")
        check = repo / "scripts/bananative.bat"
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(check), "check"], input="",
            capture_output=True, text=True, errors="replace", timeout=18)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("[MISSING]", result.stdout + result.stderr)
        self.assertNotIn("Folder [", result.stdout + result.stderr)

    def test_gradle_stage_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "stage"):
                core.gradle_command(Path(tmp), Path(tmp), "")
            stage = Path(tmp)
            for p in ("lib/libpython3.14.so", "lib/libnxpack.so", "lib/libzbicdec.so",
                      "lib/libdmsh_xlate.so", "lib/libSPIRV-Tools-shared.so", "python/lib/python3.14/os.py"):
                f = stage / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(b"x")
            repo = Path(tmp) / "repo"
            wrapper = repo / "android/app/gradlew.bat"
            wrapper.parent.mkdir(parents=True); wrapper.write_text("x")
            profile = repo / "dm/games/01006BB00C6F0000/game.tsv"
            profile.parent.mkdir(parents=True); profile.write_text("x")
            cmd = core.gradle_command(repo, stage, "01006BB00C6F0000")
            self.assertIn("-PnxGames=01006BB00C6F0000", cmd)
            self.assertEqual(cmd[-1], "apk")
            with self.assertRaises(ValueError):
                core.gradle_command(repo, stage, "oops")


class Dependencies(unittest.TestCase):
    def test_check_only_reports_without_running_installer(self):
        import dependencies as deps
        with tempfile.TemporaryDirectory() as tmp:
            found = deps.dependency_status(Path(tmp))
            self.assertEqual([x[0] for x in found], ["msys", "ucrt", "adb", "packer", "java", "sdk"])
            self.assertFalse(found[3][1])
            self.assertIn("not installed", found[3][2].lower())

    def test_adb_browse_override(self):
        import dependencies as deps
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "adb.exe"
            exe.write_bytes(b"synthetic")
            self.assertEqual(deps.adb_executable(str(exe)), str(exe.resolve()))

    def test_packer_install_requires_an_existing_folder(self):
        import dependencies as deps
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                deps.install_command("packer", Path(tmp), folder=str(Path(tmp) / "missing"))
            cmd = deps.install_command("packer", Path(tmp), folder=tmp)
            self.assertIn("-NonInteractive", cmd)
            self.assertIn("setup", cmd)


class SDKInstaller(unittest.TestCase):
    def test_detect_sdk_and_missing_components(self):
        import dependencies as deps
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Android SDK"
            root.mkdir()
            self.assertEqual(len(deps.sdk_missing(root)), 3)
            for file in ("platforms/android-36/android.jar",
                         "ndk/28.2.13676358/source.properties",
                         "build-tools/36.0.0/aapt2.exe"):
                target = root / file
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"fake test fixture")
            self.assertEqual(deps.sdk_missing(root), [])
            results = deps.dependency_status(Path(tmp), sdk_path=str(root))
            self.assertTrue(dict((key, ok) for key, ok, *_ in results)["sdk"])

    def test_sdk_install_requires_explicit_python_and_license_consent(self):
        import dependencies as deps
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = root / "localpython"
            env.mkdir()
            python = env / "python.exe"
            python.write_bytes(b"fixture")
            (root / ".bananative-env").write_text(str(env), encoding="utf-8")
            cmd = deps.install_command("sdk", root, sdk_path=str(root / "AndroidSdk"))
            self.assertEqual(cmd[0], str(python))
            self.assertIn("--license-consent", cmd)
            self.assertIn("--sdk-root", cmd)
            self.assertEqual(cmd[cmd.index("--sdk-root") + 1], str(root / "AndroidSdk"))

    def test_shader_progress_milestones(self):
        import progress
        self.assertIsNone(progress.parse("other output"))
        self.assertIsNone(progress.parse("progress 100 0 translate"))
        p = progress.parse("progress 54080 73496 translate")
        self.assertEqual(p.percent, 74)
        self.assertIn("54,080/73,496", p.text)
        milestone = progress.Milestones(step=5)
        self.assertTrue(milestone.should_log(p))
        self.assertFalse(milestone.should_log(progress.parse("progress 54120 73496 translate")))
        self.assertTrue(milestone.should_log(progress.parse("progress 55200 73496 translate")))


class Desktop(unittest.TestCase):
    def test_qt_widgets_headless(self):
        if os.environ.get("PEANUTS_STUDIO_SKIP_QT"):
            self.skipTest("Qt smoke deliberately disabled")
        try:
            from PySide6.QtWidgets import QApplication
            import app as ui
        except ImportError as exc:
            self.skipTest(str(exc))
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        qapp = QApplication.instance() or QApplication([])
        import experience
        qapp.setStyle("Fusion")
        qapp.setPalette(experience.light_palette())
        qapp.setStyleSheet(experience.CREAM_STYLE)
        win = ui.Studio()
        self.assertEqual(win.pages.count(), 9)
        self.assertIsNotNone(win.game_grid)
        self.assertIsNotNone(win.activity_bar)
        self.assertIsNotNone(win.companion_grid)
        self.assertEqual(win.nav_map["tools"], 8)
        sample = {
            "app": {"version": "0.1.3", "keys": True, "firmware": True,
                    "folders": {"game": {"path": "/sdcard/Peanut Roms"}}, "gpu_driver": "system"},
            "library": [
                {"title_id": "0100606026F12000", "name": "FINAL FANTASY RESONANCE",
                 "state": "building", "game": "game.nup", "pack": None},
                {"title_id": "01006BB00C6F0000", "name": "Link's Awakening",
                 "state": "ready", "pack": "game-pack"},
            ],
            "job": {"title_id": "0100606026F12000", "name": "FINAL FANTASY RESONANCE",
                    "state": "running", "step": "rewrite", "percent": 47,
                    "text": "Rewriting main 1 of 3", "counts":
                     {"shaders": {"done": 39800, "total": 81552}}, "eta": "38 min"},
        }
        import experience
        experience.update_overview(win, sample)
        experience.update_library(win, sample)
        experience.update_activity(win, sample)
        self.assertEqual(win.stat_total.text(), "2")
        self.assertEqual(win.stat_ready.text(), "1")
        self.assertEqual(win.activity_bar.value(), 47)
        self.assertEqual(win.game_grid.count(), 2)
        win.library_find.setText("resonance")
        self.assertEqual(win.game_grid.count(), 1)
        experience.update_companions(win, [{"title_id": "01006BB00C6F0000",
            "name": "Link's Awakening", "state": "not_installed",
            "catalog": "1.0.0", "built": True}])
        self.assertEqual(win.companion_grid.count(), 1)
        self.assertTrue(win.sources is not None)
        self.assertTrue(win.library is not None)
        from PySide6.QtGui import QPalette
        from PySide6.QtWidgets import QMessageBox
        self.assertEqual(qapp.palette().color(QPalette.ColorRole.WindowText).name(), "#38291c")
        dialog = QMessageBox(win)
        dialog.setWindowTitle("Install prerequisite")
        dialog.setText("Install Python/.NET shader packer on this PC?")
        dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        self.assertEqual(dialog.palette().color(QPalette.ColorRole.WindowText).name(), "#38291c")
        dialog.close()
        # A real 180-character Windows path must not expand the layout or
        # collide with the Install button. Full data remains in the tooltip.
        detail, install = win.dependency_rows["adb"]
        very_long = "C:\\Users\\User\\AppData\\Local\\" + ("MicrosoftWinGetPackages\\" * 9) + "adb.exe"
        detail.resize(230, 30)
        detail.set_status("✓  Ready · " + very_long, True)
        self.assertEqual(detail.toolTip(), "✓  Ready · " + very_long)
        self.assertIn("…", detail.text())
        self.assertLessEqual(detail.fontMetrics().horizontalAdvance(detail.text()), 230)
        self.assertTrue(win.console.isHidden())
        # A long shader run must remain collapsed by default, but still
        # maintain its true progress percentage and save the raw diagnostics.
        win._process_task_line("progress 54080 73496 translate")
        self.assertEqual(win.progress.value(), 74)
        self.assertIn("54,080/73,496", win.task_label.text())
        self.assertEqual(len(win._task_raw_log), 1)
        import json
        payload = {"phase": "Game file", "done": 2_400_000_000, "total": 6_000_000_000,
                   "stage_done": 900_000_000, "stage_total": 4_500_000_000,
                   "percent": 40, "rate": 38_000_000, "eta_seconds": 95,
                   "source": "device"}
        win._process_task_line("PEANUTS_TRANSFER" + chr(9) + json.dumps(payload))
        self.assertEqual(win.progress.value(), 40)
        self.assertEqual(win.transfer_progress.value(), 40)
        self.assertIn("Game file", win.task_label.text())
        self.assertIn("ETA ~1m 35s", win.task_label.text())
        self.assertIn("MiB/s", win.transfer_status.text())
        win.close()
        qapp.processEvents()


if __name__ == "__main__":
    unittest.main()
