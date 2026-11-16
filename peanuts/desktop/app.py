#!/usr/bin/env python3
"""Peanuts Studio — desktop dashboard for Windows PC builds and Android ADB control.

The existing command-line tools remain the source of truth. This GUI never
stores console keys in QSettings, never silently deletes game data, and never
assumes an ADB operation worked until the Android control status confirms it.
"""
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSpinBox,
    QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget, QHeaderView,
)

import core
import dependencies as deps
import experience

APP_NAME = "Peanuts Studio"
RE_PROGRESS = re.compile(r"^progress:? (\d+)[ /](\d+)")
DARK_STYLE = """
QMainWindow, QWidget#Main, QScrollArea { background:#0b1120; }
QWidget { color:#ebeff7; font: 12px 'Segoe UI'; }
QFrame#Sidebar { background:#101a2b; border-right:1px solid #2b394e; }
QFrame#Card { background:#151f31; border:1px solid #2d3a50; border-radius:14px; }
QLabel#PageTitle { color:#f9fbff; font-size:23px; font-weight:700; }
QLabel#Title { color:#f4f7ff; font-size:15px; font-weight:700; }
QLabel#Muted { color:#91a1ba; }
QLabel#Brand { color:#f8cb65; font-size:20px; font-weight:800; }
QLabel#Status { color:#b6c7de; }
QPushButton { background:#22324a; border:1px solid #334865; border-radius:8px;
              min-height:30px; padding:5px 12px; text-align:center; }
QPushButton:hover { background:#2f425d; }
QPushButton:pressed { background:#1c2c40; }
QPushButton:disabled { color:#73829a; background:#172234; }
QPushButton#Primary { background:#edb948; border:1px solid #f8d16b; color:#131923; font-weight:700; }
QPushButton#Primary:hover { background:#ffd06c; }
QPushButton#Nav { background:transparent; border:0; color:#a8b5ce;
                   text-align:left; padding:12px 15px; font-weight:600; }
QPushButton#Nav:checked { background:#24364d; color:#f7c862; border-left:3px solid #f0bb4b; }
QLineEdit,QTextEdit,QListWidget,QTableWidget,QComboBox,QSpinBox {
  background:#0e1829; border:1px solid #334561; border-radius:8px;
  padding:7px; selection-background-color:#e6b54c; selection-color:#152033;
}
QTableWidget { gridline-color:#273a51; }
QHeaderView::section { background:#1e2b42; color:#b8c6dc; padding:8px; border:0; }
QProgressBar { background:#202e42; border:0; border-radius:6px; min-height:10px; text-align:center; }
QProgressBar::chunk { background:#e7b54d; border-radius:6px; }
QCheckBox { spacing:10px; color:#cad5e7; }
QToolTip { background:#29364c; color:white; }
"""

def row(*items):
    h = QHBoxLayout()
    h.setSpacing(10)
    for item in items:
        if isinstance(item, QWidget):
            h.addWidget(item)
        else:
            h.addLayout(item)
    return h


def muted(text):
    w = QLabel(text)
    w.setObjectName("Muted")
    w.setWordWrap(True)
    return w


def button(text, fn, primary=False):
    b = QPushButton(text)
    if primary: b.setObjectName("Primary")
    b.clicked.connect(fn)
    return b


def labelled(title, widget):
    group = QWidget()
    layout = QVBoxLayout(group)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)
    layout.addWidget(muted(title))
    layout.addWidget(widget)
    return group


def card(title, desc=""):
    frame = QFrame()
    frame.setObjectName("Card")
    frame.setContentsMargins(0, 0, 0, 0)
    v = QVBoxLayout(frame)
    v.setContentsMargins(18, 16, 18, 18)
    v.setSpacing(12)
    label = QLabel(title)
    label.setObjectName("Title")
    v.addWidget(label)
    if desc: v.addWidget(muted(desc))
    return frame, v


def form_row(layout, label, field, add=None):
    layout.addWidget(labelled(label, field), stretch=1)
    if add is not None: layout.addWidget(add, alignment=Qt.AlignmentFlag.AlignBottom)


class Sources(QListWidget):
    changed = Signal()
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DropOnly)
        self.setMinimumHeight(105)
        self.setToolTip("Drag NSP, XCI, NUP files or dump folders here")
    def add_paths(self, paths):
        old = {self.item(i).text() for i in range(self.count())}
        for path in paths:
            p = Path(path)
            if p.exists() and (p.is_dir() or p.suffix.lower() in {".nsp", ".xci", ".nup"}):
                if str(p) not in old:
                    self.addItem(str(p)); old.add(str(p))
        self.changed.emit()
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragEnterEvent(event)
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragMoveEvent(event)
    def dropEvent(self, event):
        self.add_paths([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])
        event.acceptProposedAction()
    def selected_paths(self):
        return [self.item(i).text() for i in range(self.count())]


class Studio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.repo = core.repo_root()
        self.settings = QSettings("PeanutsNative", "Studio")
        self.msys_custom = self.settings.value("msys_root", "", type=str)
        self.adb_custom = self.settings.value("adb_exe", "", type=str)
        self.apply_saved_paths()
        self.install_queue = []
        self.install_folder = ""
        self.install_active = None
        self.task_mode = ""
        self.task_serial = 0
        self.busy = False
        self.pending_id = ""
        self.latest = {}
        self.game_data = []
        self.companion_data = []
        self.setWindowTitle(APP_NAME + "  •  Build on Windows, play on Android")
        self.resize(1370, 900)
        self.setMinimumSize(1060, 730)
        self.setWindowIcon(self.make_icon())
        self.pages = QStackedWidget()
        self.task = QProcess(self)
        self.task.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.task.readyReadStandardOutput.connect(self.task_output)
        self.task.finished.connect(self.task_finished)
        self.poll_proc = QProcess(self)
        self.poll_proc.finished.connect(self.poll_finished)
        self.control_proc = QProcess(self)
        self.control_proc.finished.connect(self.control_finished)
        self.init_ui()
        self.check_tools(log=False)
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.refresh_status)
        self.poll_timer.start(3500)
        QTimer.singleShot(500, self.refresh_devices)

    def make_icon(self):
        """Peanuts Native's green-and-gold hourglass motif, drawn as vectors."""
        pix = QPixmap(64, 64)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#21644a"))
        p.drawEllipse(3, 3, 58, 58)
        p.setBrush(QColor("#fff9df"))
        p.drawRoundedRect(23, 10, 19, 45, 9, 9)
        p.setBrush(QColor("#ffd547"))
        p.setPen(QPen(QColor("#4b321f"), 2.3))
        p.drawRoundedRect(23, 16, 19, 12, 4, 4)
        p.drawRoundedRect(23, 36, 19, 12, 4, 4)
        p.setPen(QPen(QColor("#e4b12b"), 2.1))
        p.drawArc(27, 27, 12, 10, 180 * 16, 180 * 16)
        p.end()
        return QIcon(pix)

    def init_ui(self):
        root = QWidget(); root.setObjectName("Main")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        rail = QFrame(); rail.setObjectName("Sidebar"); rail.setFixedWidth(220)
        rv = QVBoxLayout(rail); rv.setContentsMargins(12, 22, 12, 18); rv.setSpacing(9)
        brandline = QHBoxLayout()
        insignia = QLabel()
        insignia.setPixmap(self.make_icon().pixmap(54, 54))
        insignia.setFixedSize(56, 56)
        brandline.addWidget(insignia)
        brand = QLabel("PEANUTS\nSTUDIO")
        brand.setObjectName("Brand")
        brandline.addWidget(brand, 1)
        rv.addLayout(brandline)
        rv.addSpacing(23)
        self.navs = []
        names = [
            ("◈  Dashboard", "overview", self.page_overview),
            ("▦  Game library", "library", self.page_library),
            ("▣  PC builder", "builder", self.page_builder),
            ("◷  Build center", "activity", self.page_activity),
            ("▤  Android device", "device", self.page_device),
            ("✧  Companions", "companions", self.page_companions),
            ("⌘  ADB controls", "control", self.page_control),
            ("◇  APK builder", "apk", self.page_apk),
            ("⚙  Tools & setup", "tools", self.page_tools),
        ]
        self.nav_map = {key: i for i, (_, key, _) in enumerate(names)}
        for idx, (name, key, factory) in enumerate(names):
            nav = QPushButton(name)
            nav.setObjectName("Nav")
            nav.setCheckable(True)
            nav.clicked.connect(lambda checked=False, i=idx: self.show_page(i))
            rv.addWidget(nav)
            self.navs.append(nav)
            self.pages.addWidget(self.wrap_page(factory()))
        rv.addStretch()
        rv.addWidget(muted("Build locally · play on Android\nPrivate by design  •  v0.2 preview"))
        outer.addWidget(rail)
        main = QWidget(); ml = QVBoxLayout(main); ml.setContentsMargins(22, 20, 22, 16); ml.setSpacing(12)
        top = QHBoxLayout()
        t = QLabel("Peanuts Native  /  Studio"); t.setObjectName("PageTitle")
        top.addWidget(t); top.addStretch()
        self.device_combo = QComboBox(); self.device_combo.setMinimumWidth(210)
        self.device_combo.currentIndexChanged.connect(self.refresh_status)
        top.addWidget(self.device_combo)
        top.addWidget(button("↻  Devices", self.refresh_devices))
        ml.addLayout(top)
        ml.addWidget(self.pages, 1)
        console, cv = card("Activity console", "Live output from the underlying Peanuts tools. No key contents are displayed.")
        cb = QHBoxLayout()
        self.task_label = QLabel("Ready"); self.task_label.setObjectName("Status")
        cb.addWidget(self.task_label); cb.addStretch()
        cb.addWidget(button("Copy log", self.copy_log)); cb.addWidget(button("Save log", self.save_log))
        self.stop_btn = button("Stop task", self.stop_task); self.stop_btn.setEnabled(False); cb.addWidget(self.stop_btn)
        cv.addLayout(cb)
        self.progress = QProgressBar(); self.progress.setRange(0, 100)
        cv.addWidget(self.progress)
        self.console = QTextEdit(); self.console.setReadOnly(True); self.console.setFixedHeight(142)
        self.console.setFont(QFont("Consolas", 10))
        self.console.document().setMaximumBlockCount(5000)
        cv.addWidget(self.console)
        ml.addWidget(console)
        outer.addWidget(main, 1)
        self.show_page(0)

    def wrap_page(self, page):
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page); return scroll

    def show_page(self, index):
        self.pages.setCurrentIndex(index)
        for i, nav in enumerate(self.navs): nav.setChecked(i == index)

    def page(self, title, detail):
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(2, 7, 4, 16); v.setSpacing(16)
        heading = QLabel(title); heading.setObjectName("PageTitle")
        v.addWidget(heading); v.addWidget(muted(detail))
        return page, v

    def page_overview(self):
        return experience.create_overview(self)

    def page_library(self):
        return experience.create_library(self)

    def page_activity(self):
        return experience.create_activity(self)

    def page_companions(self):
        return experience.create_companions(self)

    def render_library(self, *_):
        experience.render_library(self)

    def render_companions(self, *_):
        experience.render_companions(self)

    def select_library_game(self, tid):
        if not core.TITLE.fullmatch(str(tid or "")):
            self.warn("Game selection", "This entry does not provide a supported title ID.")
            return
        self.game_id.setText(tid)
        self.show_page(self.nav_map["control"])
        self.write_log("Selected game: " + str(tid))

    def request_device_status(self):
        if self.device():
            self.control("status")
        else:
            self.write_log("[ADB] No authorized device selected. Connect the phone under Android device.")

    def fetch_companions(self):
        self.control("companion", {"do": "list", "all": "true"})

    def companion_action(self, tid, operation):
        if not core.TITLE.fullmatch(str(tid or "")):
            self.warn("Companion", "Select a valid catalog entry.")
            return
        fields = {"do": operation, "title_id": tid}
        if operation == "remove":
            if QMessageBox.question(self, "Remove companion",
                "Remove this game's companion? Game data and saves should remain untouched.") != QMessageBox.StandardButton.Yes:
                return
            fields["confirm"] = "true"
        self.control("companion", fields)

    def page_builder(self):
        page, v = self.page("Game builder", "Import your own NSP/XCI files, apply updates and DLC, build code + Vulkan shaders, optionally transfer to Android.")
        c, body = card("Game inputs", "Add the base and optional update/DLC files together. Or select one NUP or an extracted dump folder.")
        self.sources = Sources()
        body.addWidget(self.sources)
        actions = row(button("+ Add NSP / XCI / NUP files", self.add_files, True),
                      button("+ Add dump folder", self.add_folder),
                      button("Remove selected", self.remove_files),
                      button("Clear", self.sources.clear))
        body.addLayout(actions); v.addWidget(c)
        c, body = card("Build options")
        self.keys = QLineEdit(); self.keys.setPlaceholderText("Only needed when importing NSP/XCI")
        keyb = button("Browse…", self.choose_keys)
        body.addLayout(row(labelled("Console keys file (local, never saved)", self.keys), keyb))
        self.update = QLineEdit(); self.update.setPlaceholderText("Highest available (leave empty)")
        self.update.setMaximumWidth(310)
        self.nup_out = QLineEdit(); self.nup_out.setPlaceholderText("Beside the input (leave empty)")
        rr = QHBoxLayout()
        rr.addWidget(labelled("Update version (numeric)", self.update))
        rr.addWidget(labelled("NUP output file or existing folder", self.nup_out), 1)
        rr.addWidget(button("Folder…", self.choose_out), alignment=Qt.AlignmentFlag.AlignBottom)
        body.addLayout(rr)
        self.threads = QSpinBox(); self.threads.setRange(1, 128); self.threads.setValue(8)
        self.force = QCheckBox("Re-import NUP"); self.any_version = QCheckBox("Allow unprofiled update")
        self.no_shaders = QCheckBox("Code only (no shader library)")
        opt = row(labelled("Shader workers", self.threads), self.force, self.any_version, self.no_shaders)
        body.addLayout(opt)
        self.auto_push = QCheckBox("Transfer game and pack over ADB when finished")
        self.dest = QLineEdit(); self.dest.setPlaceholderText("Auto: /sdcard/Peanut Roms/<game>")
        body.addWidget(self.auto_push); body.addWidget(labelled("Custom destination on Android (optional)", self.dest))
        body.addLayout(row(button("Build + prepare", self.build_game, True),
                           button("Dry-run", lambda: self.build_game(dry=True))))
        v.addWidget(c)
        c, body = card("Decode engine", "The Windows Oodle/Unreal path is selected automatically by the existing game profile.")
        body.addWidget(muted("For supported profiles the builder compiles a separate GPL Oodle worker from pinned sources, validates all shader keys against the profile, and uses an AES adapter for encrypted Unreal indexes. If that validation fails, the pack is refused rather than silently accepted."))
        v.addWidget(c); v.addStretch(); return page

    def page_device(self):
        page, v = self.page("Android device", "ADB connection, full game-pack transfer, APK installation and diagnostic capture.")
        c, body = card("Connected phone")
        self.device_info = QLabel("No device selected"); self.device_info.setObjectName("Status")
        body.addWidget(self.device_info)
        body.addLayout(row(button("Refresh ADB", self.refresh_devices, True),
                           button("Sync device state", self.request_device_status),
                           button("Open Peanuts app", lambda: self.control("nav", {"to":"home"}))))
        v.addWidget(c)
        c, body = card("Device readiness", "Status comes from the app itself. Keys, firmware and library paths stay on the device.")
        self.device_readiness = muted("Connect an authorized device to check keys, firmware and GPU.")
        self.device_folders = muted("Game, update, DLC and build folders will appear after synchronization.")
        body.addWidget(self.device_readiness)
        body.addWidget(self.device_folders)
        body.addLayout(row(button("Open library configuration on phone", lambda: self.android_section("Library")),
                           button("Game defaults", lambda: self.android_section("Game defaults"))))
        v.addWidget(c)
        c, body = card("Transfer a prepared pack", "Choose the android-pack directory containing pack.tsv and its matching NUP/dump.")
        self.pack_path = QLineEdit(); self.pack_path.setPlaceholderText("…/<TITLEID>-work/android-pack")
        self.game_path = QLineEdit(); self.game_path.setPlaceholderText("Game.nup or dump folder")
        body.addLayout(row(labelled("Pack directory", self.pack_path), button("Folder…", lambda: self.browse_dir(self.pack_path))))
        body.addLayout(row(labelled("Game or NUP (optional)", self.game_path), button("File…", self.pick_game_transfer),
                           button("Folder…", lambda: self.browse_dir(self.game_path))))
        self.transfer_dest = QLineEdit(core.DEST)
        body.addWidget(labelled("ADB destination", self.transfer_dest))
        body.addLayout(row(button("Send to phone", self.push_existing, True),
                           button("Rescan library", lambda: self.control("scan"))))
        v.addWidget(c)
        c, body = card("APK install / logs", "APK installation may fail when the installed app is signed with a different key. Do not uninstall the existing app to force an update.")
        self.apk_to_install = QLineEdit(); self.apk_to_install.setPlaceholderText("Select a locally built Android APK")
        body.addLayout(row(self.apk_to_install, button("Browse APK", self.choose_apk)))
        body.addLayout(row(button("Install APK over ADB", self.install_apk),
                           button("Pull app logs", self.pull_logs)))
        v.addWidget(c); v.addStretch(); return page

    def page_control(self):
        page, v = self.page("Android control", "Read the app's real status and drive its approved ADB control commands. Requires the Peanuts Native Android app.")
        c, body = card("Library")
        self.library = QTableWidget(0, 4)
        self.library.setHorizontalHeaderLabels(["Game", "Status", "Title ID", "Pack"])
        self.library.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.library.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.library.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.library.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.library.setMinimumHeight(190)
        self.library.itemSelectionChanged.connect(self.selected_game)
        body.addWidget(self.library)
        self.game_id = QLineEdit(); self.game_id.setPlaceholderText("Select a row or enter a 16-character title ID")
        body.addLayout(row(labelled("Selected game", self.game_id),
                           button("Refresh status", self.request_device_status)))
        body.addLayout(row(button("Build on Android", lambda: self.game_ctl("build")),
                           button("Prepare again", lambda: self.game_ctl("prepare")),
                           button("Play", lambda: self.game_ctl("play"), True),
                           button("Scan", lambda: self.control("scan"))))
        v.addWidget(c)
        c, body = card("Job controls")
        self.job_line = muted("No active job detected.")
        body.addWidget(self.job_line)
        body.addLayout(row(button("Pause / stop", lambda: self.control("job", {"do":"pause"})),
                           button("Resume", lambda: self.control("job", {"do":"resume"})),
                           button("Retry", lambda: self.control("job", {"do":"retry"})),
                           button("Stop running game", self.stop_game)))
        v.addWidget(c)
        c, body = card("Game settings and companions")
        self.setting_key = QComboBox()
        self.setting_key.addItems(["fps_cap", "res_scale", "upscaler", "console_mode", "touch_skin", "overlay", "keep_screen_on"])
        self.setting_value = QComboBox(); self.setting_value.setEditable(True)
        self.setting_key.currentTextChanged.connect(self.setting_values)
        self.setting_values("fps_cap")
        body.addLayout(row(labelled("Setting", self.setting_key), labelled("Value", self.setting_value),
                           button("Apply selected game", self.apply_setting)))
        body.addWidget(muted("These are the settings supported by the Android app's guarded ADB interface. Other graphics, motion, controller and frame-generation options are managed in the Android UI."))
        body.addLayout(row(button("Open companion catalog", lambda: self.show_page(self.nav_map["companions"])),
                           button("Install companion", lambda: self.companion_ctl("install")),
                           button("Update companion", lambda: self.companion_ctl("update")),
                           button("Remove companion", lambda: self.companion_ctl("remove"))))
        v.addWidget(c)
        c, body = card("Open Android settings", "Navigate the real Android app for functions that its ADB bridge does not expose.")
        body.addLayout(row(button("Game defaults", lambda: self.android_section("Game defaults"), True),
                           button("Library and folders", lambda: self.android_section("Library")),
                           button("System", lambda: self.android_section("System"))))
        body.addLayout(row(button("Game performance", lambda: self.android_game_tab("performance")),
                           button("Game settings", lambda: self.android_game_tab("game")),
                           button("Saves", lambda: self.android_game_tab("saves")),
                           button("Storage", lambda: self.android_game_tab("storage"))))
        body.addWidget(muted("Advanced GPU drivers, frame generation, screen rotation, button mapping, and motion are accessible in the app's own settings, not through unsupported desktop toggles."))
        v.addWidget(c); v.addStretch(); return page

    def page_apk(self):
        page, v = self.page("APK builder", "Compile the Android app on Windows using Gradle/NDK. This does not build an Android ARM64 CPython/toolchain stage.")
        c, body = card("Required: Android ARM64 packer stage", "The real on-device Prepare engine needs prebuilt libpython3.14.so, libdmsh_xlate.so, SPIRV-Tools and other Android libraries.")
        self.stage = QLineEdit(); self.stage.setPlaceholderText("Path to an already generated stage/ directory")
        body.addLayout(row(self.stage, button("Browse stage…", lambda: self.browse_dir(self.stage))))
        self.games = QLineEdit(); self.games.setPlaceholderText("Empty = repository's default supported title IDs")
        body.addWidget(labelled("Games to include (comma-separated 16-digit IDs)", self.games))
        body.addWidget(muted("Generate the real packer stage through configured WSL2 (Linux .NET 10 SDK, zsh, Android NDK and ANDROID_NDK_HOME required). Native Windows stage generation is not implemented; no fake packer is substituted."))
        body.addLayout(row(button("Generate stage via WSL2", self.wsl_stage),
                           button("Build debug-signed APK", self.build_apk, True),
                           button("Open APK output", self.open_apk_output)))
        v.addWidget(c)
        c, body = card("Release signing", "This builder creates an installable test/development APK. Production updates require the existing release signing key and Gradle's release parameters; the GUI deliberately never asks for or saves release passwords.")
        body.addWidget(muted("Android Studio SDK/NDK, JDK 17 or 21 and Gradle's wrapper are required. The default output is android/app/out/nxnative-android-peanuts.apk."))
        v.addWidget(c); v.addStretch(); return page

    def page_tools(self):
        page, v = self.page("Tools & setup",
            "Install prerequisites from Studio. Checking never downloads anything, waits for input, or changes your system.")
        c, body = card("Dependency manager",
            "Core tools are required for Windows game packs. JDK and Android SDK/NDK are optional for building Android APKs.")
        self.dependency_rows = {}
        for key, name, action in (
            ("msys", "MSYS2 (package manager)", "Install"),
            ("ucrt", "UCRT64 compiler + CMake + zlib + patch", "Install"),
            ("adb", "Android Platform-Tools / ADB", "Install"),
            ("packer", "Python 3.14 + .NET 10 + shader packer", "Install"),
            ("java", "JDK 21 (APK build)", "Install"),
            ("sdk", "Android SDK 36 + NDK 28.2 (APK build)", "Get Android Studio"),
        ):
            line = QHBoxLayout()
            name_label = QLabel(name)
            name_label.setMinimumWidth(310)
            detail = QLabel("Not checked")
            detail.setObjectName("Muted")
            detail.setWordWrap(True)
            detail.setMinimumWidth(270)
            install = button(action, lambda checked=False, k=key: self.install_dependency(k))
            install.setMaximumWidth(170)
            line.addWidget(name_label)
            line.addWidget(detail, 1)
            line.addWidget(install)
            self.dependency_rows[key] = (detail, install)
            body.addLayout(line)
        body.addLayout(row(button("Check tools", lambda: self.check_tools(log=True), True),
                           button("Install missing core tools", self.install_missing),
                           button("Verify packer", self.verify_packer)))
        body.addWidget(muted("Installations run as visible, cancellable tasks with live logs. Winget may show a Windows elevation dialog. Full preflight compiles and tests the importer only after the required compiler is present."))
        v.addWidget(c)

        c, body = card("Custom installation paths", "Use these fields when tools were installed outside their usual locations.")
        self.msys_path = QLineEdit(self.msys_custom)
        self.msys_path.setPlaceholderText("Default: C:\\msys64")
        self.adb_path = QLineEdit(self.adb_custom)
        self.adb_path.setPlaceholderText("Automatically search ADB PATH, WinGet, Android SDK")
        body.addLayout(row(labelled("MSYS2 root", self.msys_path),
                           button("Browse…", lambda: self.browse_dir(self.msys_path))))
        body.addLayout(row(labelled("adb.exe file", self.adb_path),
                           button("Browse…", lambda: self.pick_one(self.adb_path, "Android Debug Bridge (adb.exe);;Executables (*.exe)"))))
        body.addLayout(row(button("Save paths and recheck", self.save_tool_paths),
                           button("Run full preflight", self.preflight)))
        v.addWidget(c)
        c, body = card("Repository / local files")
        body.addWidget(muted(str(self.repo)))
        body.addLayout(row(button("Open repository folder", lambda: self.open_folder(self.repo)),
                           button("Open build outputs", lambda: self.open_folder(self.repo / "peanuts/.build")),
                           button("View guide", lambda: self.open_folder(self.repo / "peanuts/docs"))))
        v.addWidget(c); v.addStretch(); return page

    def browse_dir(self, target):
        value = QFileDialog.getExistingDirectory(self, "Select folder", target.text() or str(self.repo))
        if value: target.setText(value)

    def pick_one(self, target, filter_text):
        path, _ = QFileDialog.getOpenFileName(self, "Select file", str(self.repo), filter_text)
        if path: target.setText(path)

    def choose_keys(self): self.pick_one(self.keys, "Keys (*.keys *.dat);;All files (*)")
    def choose_apk(self): self.pick_one(self.apk_to_install, "Android package (*.apk)")
    def choose_out(self): self.browse_dir(self.nup_out)
    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Game files", "", "Switch game files (*.nsp *.xci *.nup);;All files (*)")
        self.sources.add_paths(paths)
    def add_folder(self):
        f = QFileDialog.getExistingDirectory(self, "Dump folder or folder of NSP/XCI files")
        if f: self.sources.add_paths([f])
    def remove_files(self):
        for item in self.sources.selectedItems(): self.sources.takeItem(self.sources.row(item))
    def pick_game_transfer(self): self.pick_one(self.game_path, "Game package (*.nup);;All files (*)")

    def device(self): return self.device_combo.currentData()
    def write_log(self, message):
        self.console.append(message)
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

    def warn(self, title, message):
        QMessageBox.warning(self, title, str(message))
        self.write_log("[WARN] " + str(message))

    def run_task(self, cmd, label="Working", timeout_ms=0):
        if self.busy:
            self.warn("Task running", "Stop or finish the current task first.")
            return False
        self.busy = True; self.stop_btn.setEnabled(True)
        self.task_mode = label
        self.task_serial += 1
        serial = self.task_serial
        self.task_label.setText(label); self.progress.setRange(0, 0)
        self.write_log("▶  " + label)
        # Deliberately do not print command argv: it may contain the private path to keys.
        env = QProcessEnvironment()
        for key, value in core.builder_environment(self.repo).items():
            env.insert(key, value)
        if self.install_active == "ucrt":
            env.insert("MSYSTEM", "UCRT64")
            env.insert("CHERE_INVOKING", "yes")
        self.task.setProcessEnvironment(env)
        self.task.setWorkingDirectory(str(self.repo))
        self.task.start(str(cmd[0]), [str(x) for x in cmd[1:]])
        if not self.task.waitForStarted(1600):
            self.task_failed("Cannot start process: " + self.task.errorString())
            return False
        if timeout_ms:
            QTimer.singleShot(timeout_ms, lambda: self.timeout_task(serial, label))
        return True

    def timeout_task(self, serial, label):
        if not self.busy or serial != self.task_serial:
            return
        self.write_log("[TIMEOUT] " + label + " exceeded the diagnostic time limit. Stopping automatically.")
        pid = int(self.task.processId())
        if sys.platform == "win32" and pid:
            subprocess.Popen(["taskkill", "/PID", str(pid), "/T", "/F"],
                             creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            self.task.kill()

    def task_failed(self, message):
        self.busy = False; self.stop_btn.setEnabled(False)
        self.progress.setRange(0, 100); self.progress.setValue(0)
        self.task_label.setText("Failed")
        self.task_mode = ""
        self.install_queue.clear()
        self.install_active = None
        self.warn("Could not start", message)

    def task_output(self):
        output = bytes(self.task.readAllStandardOutput()).decode("utf-8", "replace")
        # Work with CR updates from native importer as well as line-oriented Python output.
        for line in output.replace("\r", "\n").splitlines():
            if not line.strip(): continue
            if self.keys.text(): line = line.replace(self.keys.text(), "[local keys path]")
            self.write_log(line)
            m = RE_PROGRESS.search(line.strip())
            if m and int(m.group(2)) > 0:
                self.progress.setRange(0, 100)
                self.progress.setValue(min(100, round(int(m.group(1)) * 100 / int(m.group(2)))))
            if line.startswith("stage: "): self.task_label.setText(line[7:].strip())

    def task_finished(self, code, status):
        completed_mode = self.task_mode
        self.task_mode = ""
        self.busy = False; self.stop_btn.setEnabled(False)
        if code == 0:
            self.progress.setRange(0, 100); self.progress.setValue(100)
            self.task_label.setText("Completed")
            self.write_log("✓  Task completed.")
        else:
            self.progress.setRange(0, 100); self.progress.setValue(0)
            self.task_label.setText("Exit code " + str(code))
            self.write_log("✗  Task exited with code " + str(code))
        if completed_mode.startswith("Verifying installed packer"):
            label, install = self.dependency_rows["packer"]
            if code == 0:
                label.setText("✓  Python, translator and SPIR-V tools verified")
                label.setStyleSheet("color:#91ddb2;")
                install.setEnabled(False)
            else:
                label.setText("✕  Packer verification failed. Choose Install to repair it.")
                label.setStyleSheet("color:#f0bd80;")
                install.setEnabled(True)
        installed = self.install_active
        self.install_active = None
        if installed:
            self.check_tools(log=False)
            if code != 0:
                self.install_queue.clear()
                self.write_log("Installation failed; remaining installation steps cancelled.")
            elif self.install_queue:
                QTimer.singleShot(250, self._install_next)
            else:
                self.write_log("Installation finished. Check the dependency status above.")
            if installed == "adb":
                QTimer.singleShot(500, self.refresh_devices)
        self.refresh_status()

    def stop_task(self):
        if not self.busy: return
        if QMessageBox.question(self, "Stop task", "Stop this task and its child processes? Completed game build steps can usually be resumed.") != QMessageBox.StandardButton.Yes:
            return
        pid = int(self.task.processId())
        if sys.platform == "win32" and pid:
            subprocess.Popen(["taskkill", "/PID", str(pid), "/T", "/F"], creationflags=subprocess.CREATE_NO_WINDOW)
        else: self.task.kill()
        self.install_queue.clear()
        self.write_log("Stopping process tree…")

    def build_game(self, dry=False):
        try:
            cmd = core.game_command(
                self.repo, core.tool_python(self.repo), self.sources.selected_paths(),
                keys=self.keys.text().strip(), update=self.update.text().strip(),
                out=self.nup_out.text().strip(), threads=self.threads.value(),
                push=self.auto_push.isChecked() and not dry, serial=self.device() or "",
                dest=self.dest.text().strip(), force=self.force.isChecked(),
                any_version=self.any_version.isChecked(), no_shaders=self.no_shaders.isChecked(),
                dry=dry)
            self.run_task(cmd, "Dry-run game build" if dry else "Importing / preparing game")
        except (ValueError, FileNotFoundError, RuntimeError) as e:
            self.warn("Build prerequisites", e)

    def refresh_devices(self):
        adb = deps.adb_executable(self.adb_custom)
        if not adb:
            self.device_info.setText("ADB not installed. Open Tools & setup and choose Install under Android Platform-Tools.")
            self.device_combo.blockSignals(True)
            self.device_combo.clear()
            self.device_combo.addItem("ADB required", None)
            self.device_combo.blockSignals(False)
            return
        try:
            p = subprocess.run([adb, "devices", "-l"], capture_output=True, text=True, timeout=6,
                               creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            if p.returncode: raise RuntimeError(p.stderr)
            serials = []
            for line in p.stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) > 1 and parts[1] == "device": serials.append(parts[0])
            previous = self.device()
            self.device_combo.blockSignals(True); self.device_combo.clear()
            self.device_combo.addItem("Select Android device", None)
            for serial in serials: self.device_combo.addItem("●  " + serial, serial)
            if previous in serials: self.device_combo.setCurrentIndex(serials.index(previous) + 1)
            elif len(serials) == 1: self.device_combo.setCurrentIndex(1)
            self.device_combo.blockSignals(False)
            self.device_info.setText("Authorized ADB devices: " + (", ".join(serials) if serials else "none"))
            if self.device():
                self.request_device_status()
        except (OSError, subprocess.SubprocessError, RuntimeError) as e:
            self.device_info.setText("ADB unavailable: " + str(e))
            self.write_log("[ADB] " + str(e))

    def refresh_status(self, *_):
        serial = self.device()
        if not serial or self.poll_proc.state() != QProcess.ProcessState.NotRunning: return
        cmd = core.status_command(serial)
        self.poll_proc.start(cmd[0], cmd[1:])

    def poll_finished(self, code, status):
        if code: return
        raw = bytes(self.poll_proc.readAllStandardOutput()).decode("utf-8", "replace")
        try: data = json.loads(raw)
        except (ValueError, TypeError): return
        self.latest = data
        experience.update_overview(self, data)
        experience.update_library(self, data)
        experience.update_activity(self, data)
        app = data.get("app") or {}
        self.device_readiness.setText(
            "Peanuts Native " + str(app.get("version") or "?") +
            "   •   Keys " + ("configured" if app.get("keys") else "missing") +
            "   •   Firmware " + ("configured" if app.get("firmware") else "missing") +
            "   •   GPU " + str(app.get("gpu_driver") or "system"))
        paths = []
        for label, key in (("Games", "game"), ("Updates", "update"), ("DLC", "dlc"), ("Build", "build")):
            folder = (app.get("folders") or {}).get(key) or {}
            path = folder.get("path") if isinstance(folder, dict) else ""
            free = experience.human_bytes(folder.get("free")) if isinstance(folder, dict) else "—"
            paths.append(f"{label}: {path or 'not selected'}  •  free: {free}")
        self.device_folders.setText("\n".join(paths))
        self.overview_status.setText(
            "Android: " + str(app.get("version", "?")) +
            "    •    Keys: " + str(app.get("keys", "?")) +
            "    •    Firmware: " + str(app.get("firmware", "?")) +
            "    •    Library games: " + str(len(data.get("library") or [])))
        job = data.get("job") or {}
        build = data.get("build") or {}
        self.job_line.setText(
            ("Prepare: " + str(job.get("name", "")) + " / " + str(job.get("step", "")) +
             " / " + str(job.get("percent", "?")) + "% (" + str(job.get("state", "")) + ")")
            if job else ("PC/Android build: " + str(build.get("step", "?"))) if build.get("running") else "No active job detected.")
        self.display_library(data.get("library") or [])
        result = data.get("last_result") or {}
        if result.get("id") == self.pending_id and not result.get("pending", False):
            self.pending_id = ""
            self.write_log("[Android control] " + ("OK" if result.get("ok") else "Failed") +
                           " — " + str(result.get("message") or result.get("error") or result.get("cmd") or ""))
            extra = result.get("data")
            if extra and result.get("cmd") == "companion":
                if isinstance(extra, dict) and isinstance(extra.get("companions"), list):
                    experience.update_companions(self, extra["companions"])
                else:
                    self.write_log(json.dumps(extra, ensure_ascii=False, indent=2)[:1800])

    def display_library(self, library):
        chosen = self.game_id.text().strip()
        self.library.blockSignals(True)
        self.library.setRowCount(len(library))
        for i, entry in enumerate(library):
            values = [str(entry.get("name", "")), str(entry.get("state", "")),
                      str(entry.get("title_id", "")), str(entry.get("pack", "") or "")]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col == 1:
                    cell.setForeground(QColor("#96d7ac") if value == "ready" else QColor("#eac27a"))
                self.library.setItem(i, col, cell)
        self.library.blockSignals(False)

    def selected_game(self):
        items = self.library.selectedItems()
        if items:
            row_num = items[0].row()
            item = self.library.item(row_num, 2)
            if item: self.game_id.setText(item.text())

    def control(self, action, fields=None):
        serial = self.device()
        if not serial:
            self.warn("ADB", "Connect and select an authorized Android device.")
            return
        if self.control_proc.state() != QProcess.ProcessState.NotRunning:
            self.write_log("ADB control request still running"); return
        try:
            self.pending_id = uuid.uuid4().hex[:12]
            cmd = core.control_command(serial, action, fields, self.pending_id)
            self.write_log("[Android] " + action + " " + json.dumps(fields or {}, ensure_ascii=False))
            self.control_proc.start(cmd[0], cmd[1:])
        except ValueError as e:
            self.warn("Control", e)

    def control_finished(self, code, status):
        if code: self.write_log("[ADB] Control command failed (exit " + str(code) + ")")
        QTimer.singleShot(650, self.refresh_status)

    def android_section(self, section):
        self.control("nav", {"to": "settings", "section": section})

    def android_game_tab(self, tab):
        tid = self.game_id.text().strip().upper()
        if not core.TITLE.fullmatch(tid):
            self.warn("Select game", "Select a game first to open its Android settings.")
            return
        self.control("nav", {"to": "game", "title_id": tid, "tab": tab})

    def game_ctl(self, action):
        tid = self.game_id.text().strip().upper()
        if not core.TITLE.fullmatch(tid):
            self.warn("Select game", "Select a game from the library or enter its 16-character title ID.")
            return
        self.control(action, {"title_id":tid})

    def stop_game(self):
        if QMessageBox.question(self, "Stop running game", "Unsaved game progress may be lost. Stop the game?") == QMessageBox.StandardButton.Yes:
            self.control("game", {"do":"stop","confirm":"true"})

    def setting_values(self, key):
        opts = {"fps_cap":["default","own","60","45","40","30","20","15"],
                "res_scale":["default","0.5","0.75","1","1.25","1.5","2"],
                "upscaler":["default","nearest","bilinear","fsr1","native","sgsr1"],
                "console_mode":["default","docked","handheld"],
                "touch_skin":["switch","dualsense"],
                "overlay":["on","off"],"keep_screen_on":["on","off"]}
        self.setting_value.clear(); self.setting_value.addItems(opts.get(key, []))

    def apply_setting(self):
        fields = {"key":self.setting_key.currentText(), "value":self.setting_value.currentText()}
        tid = self.game_id.text().strip().upper()
        if tid and core.TITLE.fullmatch(tid) and fields["key"] not in ("overlay", "keep_screen_on", "touch_skin"):
            fields["title_id"] = tid
        self.control("set", fields)

    def companion_ctl(self, operation):
        tid = self.game_id.text().strip().upper()
        if not core.TITLE.fullmatch(tid):
            self.warn("Select game", "Select a game before changing companions."); return
        fields = {"do":operation, "title_id":tid}
        if operation == "remove":
            if QMessageBox.question(self, "Remove companion", "Remove the companion package for this game?") != QMessageBox.StandardButton.Yes:
                return
            fields["confirm"] = "true"
        self.control("companion", fields)

    def push_existing(self):
        pack = Path(self.pack_path.text().strip())
        if not (pack / "pack.tsv").is_file():
            self.warn("Pack missing", "Choose the android-pack folder containing pack.tsv."); return
        serial = self.device()
        if not serial: self.warn("ADB", "Select an authorized device."); return
        cmd = [sys.executable if not getattr(sys, "frozen", False) else "",
               str(self.repo / "peanuts/scripts/push-pack.py"), str(pack), "--serial", serial]
        try: cmd[0] = core.tool_python(self.repo)
        except RuntimeError as e: self.warn("Python environment", e); return
        if self.game_path.text().strip():
            cmd += ["--game", self.game_path.text().strip()]
        dest = self.transfer_dest.text().strip()
        if dest: cmd += ["--dest", dest]
        self.run_task(cmd, "ADB transfer")

    def install_apk(self):
        serial = self.device()
        apk = Path(self.apk_to_install.text().strip())
        if not serial or not apk.is_file() or apk.suffix.lower() != ".apk":
            self.warn("APK install", "Select an Android device and an existing APK."); return
        if QMessageBox.question(self, "Install Android APK",
                                "Install this APK with adb install -r? A different signing key may prevent updating the installed app. No uninstall will be performed.") != QMessageBox.StandardButton.Yes:
            return
        self.run_task(core.adb_command(serial, ["install", "-r", str(apk)]), "Installing Android APK")

    def pull_logs(self):
        serial = self.device()
        if not serial: self.warn("ADB", "Select a device."); return
        where = QFileDialog.getExistingDirectory(self, "Folder for logs")
        if where:
            self.run_task(core.adb_command(serial, ["pull", "/sdcard/Android/data/" + core.PACKAGE + "/files/logs", where]), "Pulling Android logs")

    def wsl_stage(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose a Windows work folder (stage will be stored in its stage/ subfolder)")
        if not folder: return
        try:
            cmd = core.wsl_stage_command(self.repo, folder)
            self.stage.setText(str(Path(folder) / "stage"))
            self.run_task(cmd, "Building real Android ARM64 packer stage in WSL2")
        except (RuntimeError, ValueError) as e:
            self.warn("WSL2 stage prerequisites", e)

    def build_apk(self):
        try: cmd = core.gradle_command(self.repo, self.stage.text().strip(), self.games.text().strip())
        except (ValueError, FileNotFoundError) as e: self.warn("Android stage", e); return
        self.run_task(cmd, "Building debug-signed Android APK")

    def open_apk_output(self): self.open_folder(self.repo / "android/app/out")

    def open_folder(self, path):
        path = Path(path)
        if not path.exists(): self.warn("Folder", "Path does not exist: " + str(path)); return
        if os.name == "nt": os.startfile(str(path))
        else: subprocess.Popen(["xdg-open", str(path)])

    def apply_saved_paths(self):
        if self.msys_custom:
            os.environ["PEANUTS_MSYS2_ROOT"] = self.msys_custom
            os.environ["PEANUTS_MSYS2_UCRT64"] = str(Path(self.msys_custom) / "ucrt64/bin")
        if self.adb_custom:
            os.environ["PEANUTS_ADB"] = self.adb_custom

    def save_tool_paths(self):
        self.msys_custom = self.msys_path.text().strip()
        self.adb_custom = self.adb_path.text().strip()
        self.settings.setValue("msys_root", self.msys_custom)
        self.settings.setValue("adb_exe", self.adb_custom)
        for key in ("PEANUTS_MSYS2_ROOT", "PEANUTS_MSYS2_UCRT64", "PEANUTS_ADB"):
            os.environ.pop(key, None)
        self.apply_saved_paths()
        self.check_tools()
        self.refresh_devices()

    def check_tools(self, log=True):
        """Read-only, finite, synchronous file checks. No setup, prompts or downloads."""
        results = deps.dependency_status(self.repo, adb=self.adb_custom, root=self.msys_custom)
        self.dep_results = {key: (ok, detail, optional) for key, ok, detail, optional in results}
        for key, ok, detail, optional in results:
            label, install = self.dependency_rows[key]
            label.setText(("✓  " if ok else "✕  ") + detail)
            label.setStyleSheet("color:" + ("#91ddb2" if ok else "#f0bd80") + ";")
            install.setEnabled(not ok)
            if log:
                self.write_log(("[OK] " if ok else "[MISSING] ") + key + ": " + detail)
        if log:
            self.write_log("Dependency scan finished. Nothing was installed or changed.")
            if self.dep_results["packer"][0] and not self.busy:
                QTimer.singleShot(0, self.verify_packer)
        return self.dep_results

    def install_missing(self):
        if self.busy:
            self.warn("Task running", "Finish or stop the current task before installing dependencies.")
            return
        results = self.check_tools(log=False)
        missing = [k for k in ("msys", "ucrt", "adb", "packer") if not results[k][0]]
        if not missing:
            self.write_log("All core tools appear installed. Run Verify packer for full verification.")
            return
        if QMessageBox.question(self, "Install core prerequisites",
                                "Install: " + ", ".join(missing) + "?\n\n"
                                "This uses Windows Package Manager, MSYS2 pacman, and the project's packer installer. "
                                "You may need a network connection and Windows may request elevation.") != QMessageBox.StandardButton.Yes:
            return
        if "packer" in missing:
            folder = QFileDialog.getExistingDirectory(self, "Choose a folder for the Python/.NET packer environment", str(Path.home()))
            if not folder:
                return
            self.install_folder = folder
        self.install_queue = missing
        self._install_next()

    def install_dependency(self, kind):
        if self.busy:
            self.warn("Task running", "Stop or finish the current task before starting an installation.")
            return
        install_kind = "studio" if kind == "sdk" else kind
        names = {"msys":"MSYS2", "ucrt":"MSYS2 UCRT64 toolchain", "adb":"Android Platform-Tools (ADB)",
                 "packer":"Python/.NET shader packer", "java":"Temurin JDK 21", "studio":"Android Studio"}
        if QMessageBox.question(self, "Install prerequisite", "Install " + names[install_kind] +
                                " on this PC? This downloads official packages; elevation may be required.") != QMessageBox.StandardButton.Yes:
            return
        if install_kind == "packer":
            folder = QFileDialog.getExistingDirectory(self, "Select folder for packer files", str(Path.home()))
            if not folder: return
            self.install_folder = folder
        self.install_queue = [install_kind]
        self._install_next()

    def _install_next(self):
        if not self.install_queue:
            return
        kind = self.install_queue.pop(0)
        try:
            cmd = deps.install_command(kind, self.repo, root=self.msys_custom, folder=self.install_folder)
        except (ValueError, RuntimeError) as exc:
            self.install_queue.clear()
            self.warn("Installation prerequisites", exc)
            return
        self.install_active = kind
        if not self.run_task(cmd, "Installing " + kind):
            self.install_active = None

    def verify_packer(self):
        """Run the real packer checker; it now exits without auto-install or stdin."""
        if self.busy:
            self.warn("Task running", "Finish the active task first.")
            return
        if not self.check_tools(log=False).get("packer", (False,))[0]:
            self.warn("Packer not installed", "Choose Install next to Python/.NET shader packer first.")
            return
        self.run_task(["cmd.exe", "/d", "/c", str(self.repo / "scripts/bananative.bat"), "check"],
                      "Verifying installed packer (no changes)", timeout_ms=60000)

    def preflight(self):
        if self.busy:
            self.warn("Task running", "Finish the active task first.")
            return
        check = self.check_tools(log=False)
        missing = [key for key in ("msys", "ucrt", "packer") if not check[key][0]]
        if missing:
            self.write_log("[MISSING] Preflight cannot run: " + ", ".join(missing) +
                           ". Install the missing dependencies above first.")
            self.show_page(self.nav_map["tools"])
            return
        self.run_task(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                       "-File", str(self.repo / "peanuts/scripts/windows-builder-check.ps1")],
                      "Windows toolchain preflight")

    def setup_env(self):
        self.install_dependency("packer")

    def check_env(self):
        self.check_tools()

    def copy_log(self): QApplication.clipboard().setText(self.console.toPlainText())
    def save_log(self):
        f, _ = QFileDialog.getSaveFileName(self, "Save activity", "peanuts-studio-log.txt", "Text files (*.txt)")
        if f: Path(f).write_text(self.console.toPlainText() + "\n", encoding="utf-8")

    def closeEvent(self, event):
        if self.busy:
            answer = QMessageBox.question(self, "Task running", "A task is running. Stop it and close?")
            if answer != QMessageBox.StandardButton.Yes: event.ignore(); return
            self.stop_task()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(experience.CREAM_STYLE)
    try: win = Studio()
    except (OSError, FileNotFoundError) as e:
        QMessageBox.critical(None, "Peanuts Studio", str(e))
        return 2
    win.show()
    if '--preview' in sys.argv:
        # Actual UI capture on the Windows CI runner, without a mock device or fake library.
        at = sys.argv.index('--preview')
        destination = sys.argv[at + 1] if at + 1 < len(sys.argv) else 'PeanutsStudio-preview.png'
        def capture():
            win.show_page(win.nav_map["overview"])
            app.processEvents()
            win.grab().save(destination, "PNG")
            app.quit()
        QTimer.singleShot(900, capture)
    elif '--smoke' in sys.argv:
        QTimer.singleShot(800, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
