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
        self.assertEqual(cmd[:4], ["adb", "-s", "serial-A", "shell"])
        self.assertIn("dev.nxnative.android.peanuts/dev.peanuts.ctl.Command", cmd)
        self.assertIn("abc123", cmd)
        with self.assertRaises(ValueError):
            core.control_command("abc 1", "status")
        with self.assertRaises(ValueError):
            core.control_command("abc", "status;rm")
        with self.assertRaises(ValueError):
            core.control_command("abc", "status", {"bad;key":"a"})

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
        win = ui.Studio()
        self.assertEqual(win.pages.count(), 6)
        self.assertTrue(win.sources is not None)
        self.assertTrue(win.library is not None)
        win.close()
        qapp.processEvents()


if __name__ == "__main__":
    unittest.main()
