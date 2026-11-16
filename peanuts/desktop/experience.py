"""Peanuts Studio's modern desktop experience.

These views render *only* information returned by the Android control status
file and companion catalog; a missing device means an empty library, not a
pretend set of games. Commands are delegated to Studio's guarded ADB bridge.
"""
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QProgressBar, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

CREAM_STYLE = """
QMainWindow, QWidget#Main, QScrollArea { background:#fbf6e9; }
QDialog, QMessageBox { background-color:#fffaf0; color:#38291c; }
QDialog QLabel, QMessageBox QLabel { color:#38291c; background:transparent; font-size:14px; }
QMessageBox QLabel#qt_msgbox_label { color:#38291c; min-width:340px; }
QMessageBox QPushButton { min-width:80px; min-height:32px; font-size:13px; }
QWidget#PageSurface { background:#fbf6e9; }
QWidget { color:#38291c; font: 13px 'Segoe UI'; }
QFrame#Sidebar { background:#fffdf8; border-right:1px solid #ecdfc1; }
QFrame#Card { background:#fffdfa; border:1px solid #e8d8b9; border-radius:17px; }
QFrame#Hero { background:#fff0bd; border:1px solid #f2d47e; border-radius:22px; }
QFrame#Tile { background:#fffefa; border:1px solid #e9dfc7; border-radius:18px; }
QFrame#Metric { background:#fffdfa; border:1px solid #ebe0c8; border-radius:15px; }
QFrame#ActivityBar { background:#fffdfa; border:1px solid #e8d8b9; border-radius:13px; }
QFrame#ToolRow { background:#fffaf1; border:1px solid #f0e4ca; border-radius:11px; }
QLabel#ToolName { color:#463323; font-size:13px; font-weight:650; }
QLabel#ToolReady { color:#196844; font-size:13px; font-weight:650; }
QLabel#ToolMissing { color:#94611b; font-size:13px; font-weight:650; }
QLabel#PageTitle { color:#35281b; font-size:25px; font-weight:750; }
QLabel#Title { color:#342819; font-size:15px; font-weight:700; }
QLabel#Muted { color:#6e5d48; }
QLabel#Brand { color:#8d570f; font-size:21px; font-weight:800; }
QLabel#Status { color:#765f46; }
QLabel#MetricValue { color:#493018; font-size:27px; font-weight:750; }
QLabel#Eyebrow { color:#a0742b; font-size:11px; font-weight:700; }
QLabel#HeroTitle { color:#3d2917; font-size:25px; font-weight:750; }
QLabel#TileTitle { color:#422e20; font-size:14px; font-weight:750; }
QLabel#Pill { color:#88601f; background:#fff0b4; border-radius:11px; padding:5px 9px; font-weight:650; }
QLabel#Ready { color:#216b4d; background:#e7f3e9; border-radius:11px; padding:5px 9px; font-weight:650; }
QLabel#Running { color:#865d16; background:#fff1bf; border-radius:11px; padding:5px 9px; font-weight:650; }
QLabel#Failed { color:#9a3a2a; background:#fce9e1; border-radius:11px; padding:5px 9px; font-weight:650; }
QPushButton { background:#fff9e9; border:1px solid #eadcbf; border-radius:10px;
              min-height:30px; padding:6px 13px; color:#56432c; font-weight:600; }
QPushButton:hover { background:#fff1c9; border-color:#dfb75c; }
QPushButton:pressed { background:#f9e2a2; }
QPushButton:disabled { color:#766d5f; background:#f3ecdd; border-color:#e6dac2; }
QPushButton#Primary { background:#ffd548; border:1px solid #f6c62f; color:#352614; font-weight:750; }
QPushButton#Primary:hover { background:#ffe078; }
QPushButton#Nav { background:transparent; border:0; color:#79674f; text-align:left;
                   padding:12px 16px; font-weight:650; border-radius:10px; }
QPushButton#Nav:hover { background:#fbf0d5; }
QPushButton#Nav:checked { background:#ffedb6; color:#704916; border-left:3px solid #eebd34; }
QLineEdit,QTextEdit,QListWidget,QTableWidget,QComboBox,QSpinBox {
  background:#fffdf7; border:1px solid #e4d8bf; border-radius:10px;
  padding:8px; color:#3d3224; selection-background-color:#f7d675; selection-color:#443019;
}
QLineEdit:focus,QComboBox:focus { border:1px solid #dbab44; }
QTableWidget { gridline-color:#efe4cd; }
QHeaderView::section { background:#f9edd5; color:#795d34; padding:8px; border:0; }
QProgressBar { background:#eee4cd; border:0; border-radius:6px; min-height:9px; text-align:center; color:#634616; }
QProgressBar::chunk { background:#f6c734; border-radius:6px; }
QCheckBox { spacing:10px; color:#6c5639; }
QToolTip { background:#51402b; color:#fff9eb; border:0; padding:7px; }
QScrollBar:vertical { background:#fbf6e9; width:11px; }
QScrollBar::handle:vertical { background:#dbc6a3; border-radius:5px; min-height:30px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
"""


def light_palette():
    """Force readable native dialogs even when Windows system theme is dark."""
    p = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, "#fffaf0"),
        (QPalette.ColorRole.WindowText, "#38291c"),
        (QPalette.ColorRole.Base, "#fffdf7"),
        (QPalette.ColorRole.AlternateBase, "#fbf3e2"),
        (QPalette.ColorRole.Text, "#38291c"),
        (QPalette.ColorRole.Button, "#fff5df"),
        (QPalette.ColorRole.ButtonText, "#38291c"),
        (QPalette.ColorRole.ToolTipBase, "#51402b"),
        (QPalette.ColorRole.ToolTipText, "#fff9eb"),
        (QPalette.ColorRole.Highlight, "#f7d675"),
        (QPalette.ColorRole.HighlightedText, "#38291c"),
        (QPalette.ColorRole.PlaceholderText, "#82705c"),
    ):
        p.setColor(role, QColor(color))
    return p


def button(title, callback, primary=False):
    b = QPushButton(title)
    if primary:
        b.setObjectName("Primary")
    b.clicked.connect(callback)
    return b


def subtitle(text):
    item = QLabel(str(text))
    item.setObjectName("Muted")
    item.setWordWrap(True)
    return item


def textlabel(text, name="Title"):
    item = QLabel(str(text))
    item.setObjectName(name)
    item.setWordWrap(True)
    return item


def section(title, lead=""):
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(4, 4, 4, 14)
    v.setSpacing(13)
    v.addWidget(textlabel(title, "PageTitle"))
    if lead:
        v.addWidget(subtitle(lead))
    return w, v


def panel(title=None, lead=None, style="Card"):
    frame = QFrame()
    frame.setObjectName(style)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(21, 19, 21, 19)
    layout.setSpacing(11)
    if title:
        layout.addWidget(textlabel(title))
    if lead:
        layout.addWidget(subtitle(lead))
    return frame, layout


def inline(*items):
    h = QHBoxLayout()
    h.setSpacing(9)
    for obj in items:
        if isinstance(obj, QWidget):
            h.addWidget(obj)
        else:
            h.addLayout(obj)
    return h


def metric(name, value="—", detail=""):
    box, body = panel(style="Metric")
    label = textlabel(str(value), "MetricValue")
    body.addWidget(textlabel(name, "Eyebrow"))
    body.addWidget(label)
    body.addWidget(subtitle(detail))
    return box, label


def human_bytes(value):
    try:
        x = float(value)
        if x < 0:
            return "—"
        for unit in ("B", "KB", "GB", "TB"):
            if unit == "KB":
                x /= 1024.
            elif unit in ("GB", "TB"):
                x /= 1024.
            if x < 1024 or unit == "TB":
                return f"{x:.1f} {unit}" if unit != "B" else f"{int(x)} B"
    except (TypeError, ValueError):
        pass
    return "—"


def normalize_job(data):
    """Minimal, lossless representation of Android Status.java's two job types."""
    job = data.get("job") or {}
    build = data.get("build") or {}
    active = bool(build.get("running"))
    if job and job.get("state") in ("running", "pending", "paused", "failed"):
        return {
            "type": "Android Prepare",
            "title": job.get("name") or job.get("title_id") or "Preparing game",
            "state": str(job.get("state") or "unknown"),
            "step": job.get("step") or "Preparing",
            "percent": max(0, min(100, int(job.get("percent") or 0))),
            "detail": job.get("text") or "",
            "eta": job.get("eta"),
            "error": job.get("error_detail") or job.get("error") or "",
            "counts": job.get("counts") or {},
            "path": job.get("job_file") or "",
            "log": job.get("log") or "",
        }
    if active:
        return {
            "type": "Android Build",
            "title": build.get("name") or build.get("title_id") or "Building game",
            "state": "running",
            "step": build.get("step") or "Building",
            "percent": max(0, min(100, int(build.get("percent") or 0))),
            "detail": build.get("detail") or "",
            "eta": None, "error": "", "counts": {}, "path": "", "log": "",
        }
    return None


def library_rows(data):
    return [x for x in (data.get("library") or []) if isinstance(x, dict)]


def readiness(data):
    app = data.get("app") or {}
    rows = library_rows(data)
    ready = sum(1 for x in rows if x.get("state") == "ready")
    building = sum(1 for x in rows if x.get("state") == "building")
    return len(rows), ready, building, bool(app.get("keys")), bool(app.get("firmware"))


class GameTile(QFrame):
    def __init__(self, entry, select, percent=None):
        super().__init__()
        self.setObjectName("Tile")
        self.setMinimumHeight(164)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 17, 16, 15)
        v.setSpacing(9)
        state = entry.get("state") or "unknown"
        name = str(entry.get("name") or "Unknown game")
        tid = str(entry.get("title_id") or "")
        head = QHBoxLayout()
        title_card = QLabel(name[0].upper() if name else "●")
        title_card.setFixedSize(46, 46)
        title_card.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_card.setStyleSheet(
            "background:#ffdf72;color:#69491d;border-radius:14px;"
            "font-size:22px;font-weight:800;")
        head.addWidget(title_card)
        head.addStretch()
        badge = textlabel({
            "ready": "Ready", "building": "Building", "build": "Build needed",
            "not_in_app": "Not in APK"}.get(state, state.capitalize()),
            "Ready" if state == "ready" else "Running" if state in ("building", "build")
            else "Failed" if state == "not_in_app" else "Pill")
        head.addWidget(badge)
        v.addLayout(head)
        title = textlabel(name, "TileTitle")
        title.setMinimumHeight(32)
        v.addWidget(title)
        v.addWidget(subtitle(tid))
        if state == "building" and percent is not None:
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(max(0, min(100, int(percent))))
            bar.setFormat(f"Preparing  ·  {int(percent)}%")
            bar.setTextVisible(True)
            v.addWidget(bar)
        v.addStretch()
        footer = button("Manage game  ›", lambda: select(tid))
        v.addWidget(footer)


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            clear_layout(item.layout())


def create_overview(studio):
    page, v = section("Your Peanuts workspace", "An organized view of the games and builds on your Android phone, with the heavy lifting done on your Windows PC.")
    hero, hv = panel(style="Hero")
    hv.addWidget(textlabel("BUILD ON PC   •   PLAY ON ANDROID", "Eyebrow"))
    hv.addWidget(textlabel("Your games. One place.", "HeroTitle"))
    hv.addWidget(subtitle("Import and prepare games on Windows, transfer safely over ADB, or follow the Android build already running on your phone."))
    hv.addLayout(inline(
        button("＋  Prepare a game", lambda: studio.show_page(studio.nav_map["builder"]), True),
        button("View game library", lambda: studio.show_page(studio.nav_map["library"])),
        button("Check dependencies", lambda: studio.show_page(studio.nav_map["tools"]))))
    v.addWidget(hero)
    stats = QHBoxLayout()
    studio.stat_total = studio.stat_ready = studio.stat_building = studio.stat_device = None
    for key, label, detail in (("stat_total", "IN LIBRARY", "Games on your phone"),
                                ("stat_ready", "READY", "Play-ready packs"),
                                ("stat_building", "BUILDING", "Current Android jobs"),
                                ("stat_device", "DEVICE", "ADB connection")):
        item, val = metric(label, "—", detail)
        setattr(studio, key, val)
        stats.addWidget(item)
    v.addLayout(stats)
    build, bv = panel("Current build", "Live Android status, refreshed from your connected phone. A PC build uses the activity console below.")
    studio.home_build = textlabel("No Android build running")
    studio.home_build_detail = subtitle("Connect a phone or start a supported Prepare job.")
    studio.home_bar = QProgressBar()
    studio.home_bar.setRange(0, 100)
    studio.home_bar.setValue(0)
    bv.addWidget(studio.home_build)
    bv.addWidget(studio.home_build_detail)
    bv.addWidget(studio.home_bar)
    bv.addLayout(inline(button("Open build center", lambda: studio.show_page(studio.nav_map["activity"]), True),
                        button("Sync status", studio.request_device_status)))
    v.addWidget(build)
    bottom = QHBoxLayout()
    setup, sv = panel("Phone readiness")
    studio.home_readiness = subtitle("Device not yet connected.")
    sv.addWidget(studio.home_readiness)
    sv.addLayout(inline(button("Connect device", lambda: studio.show_page(studio.nav_map["device"])),
                        button("Tools & setup", lambda: studio.show_page(studio.nav_map["tools"]))))
    bottom.addWidget(setup)
    tip, tv = panel("How Peanuts builds")
    tv.addWidget(subtitle("PC builder → Import / rewrite code / translate shaders / transfer pack"))
    tv.addWidget(subtitle("Android Prepare → Native on-device packer / game-specific work / ready"))
    tv.addWidget(subtitle("Ready is reported only when the Android app confirms the pack can be launched."))
    bottom.addWidget(tip)
    v.addLayout(bottom)
    v.addStretch()
    return page


def create_library(studio):
    page, v = section("Game library", "Your device's actual Peanuts Native library. Game information comes from the Android app, not from a guessed catalog.")
    toolbar, body = panel()
    studio.library_summary = subtitle("Connect an Android phone to load its library.")
    body.addWidget(studio.library_summary)
    tool = QHBoxLayout()
    studio.library_find = QLineEdit()
    studio.library_find.setPlaceholderText("Search by game name or title ID…")
    studio.library_find.textChanged.connect(studio.render_library)
    studio.library_filter = QComboBox()
    studio.library_filter.addItems(["All games", "Ready", "Building", "Build needed", "Not in APK"])
    studio.library_filter.currentIndexChanged.connect(studio.render_library)
    studio.library_filter.setMinimumWidth(140)
    tool.addWidget(studio.library_find, 1)
    tool.addWidget(studio.library_filter)
    tool.addWidget(button("↻  Refresh", studio.request_device_status))
    body.addLayout(tool)
    v.addWidget(toolbar)
    studio.game_grid = QGridLayout()
    studio.game_grid.setSpacing(14)
    studio.game_grid.setContentsMargins(2, 6, 2, 10)
    v.addLayout(studio.game_grid)
    studio.library_empty = subtitle("No games reported by the connected Android app.")
    v.addWidget(studio.library_empty)
    v.addStretch()
    return page


def create_activity(studio):
    page, v = section("Build center", "Follow the Android game's real steps, counts and status. Jobs and progress are never simulated.")
    c, body = panel("Android build / Prepare job", "The Android app writes a status snapshot every few seconds while work runs.")
    studio.activity_title = textlabel("No active job")
    studio.activity_state = textlabel("Idle", "Pill")
    studio.activity_step = subtitle("Start a supported game build or connect to an Android phone.")
    studio.activity_bar = QProgressBar()
    studio.activity_bar.setRange(0, 100)
    studio.activity_bar.setValue(0)
    studio.activity_count = subtitle("")
    body.addLayout(inline(studio.activity_title, studio.activity_state))
    body.addWidget(studio.activity_step)
    body.addWidget(studio.activity_bar)
    body.addWidget(studio.activity_count)
    body.addLayout(inline(
        button("Pause", lambda: studio.control("job", {"do": "pause"})),
        button("Resume", lambda: studio.control("job", {"do": "resume"})),
        button("Retry", lambda: studio.control("job", {"do": "retry"})),
        button("↻  Refresh", studio.request_device_status)))
    v.addWidget(c)
    c, body = panel("Job diagnostics")
    studio.activity_error = subtitle("Any error, recorded job path and log path will appear here.")
    body.addWidget(studio.activity_error)
    body.addWidget(subtitle("You can pull Android logs under Android device. Local PC builder logs appear in the activity console."))
    v.addWidget(c)
    c, body = panel("Prepare somewhere else", "Send a game to your phone after preparing it on the computer; or use the Android build engine if a profile requires on-device work.")
    body.addLayout(inline(button("Windows game builder", lambda: studio.show_page(studio.nav_map["builder"]), True),
                          button("ADB controls", lambda: studio.show_page(studio.nav_map["control"]))))
    v.addWidget(c)
    v.addStretch()
    return page


def create_companions(studio):
    page, v = section("Companions", "Browse the catalog on your phone, then install or update only through its verified companion manager.")
    c, body = panel("Connected catalog", "The catalog is fetched by the Android app and requires a phone connection and network.")
    studio.companion_summary = subtitle("Catalog not loaded. Connect your phone, then refresh.")
    body.addWidget(studio.companion_summary)
    body.addLayout(inline(button("↻  Fetch catalog", studio.fetch_companions, True),
                          button("Refresh library", studio.request_device_status)))
    studio.companion_find = QLineEdit()
    studio.companion_find.setPlaceholderText("Search companions by name or title ID…")
    studio.companion_find.textChanged.connect(studio.render_companions)
    body.addWidget(studio.companion_find)
    v.addWidget(c)
    studio.companion_grid = QGridLayout()
    studio.companion_grid.setContentsMargins(2, 4, 2, 8)
    studio.companion_grid.setSpacing(12)
    v.addLayout(studio.companion_grid)
    studio.companion_empty = subtitle("No catalog entries loaded yet.")
    v.addWidget(studio.companion_empty)
    v.addStretch()
    return page


def update_overview(studio, data):
    total, ready, building, keys, firmware = readiness(data)
    if not data:
        vals = ("—", "—", "—", "Offline")
        studio.home_readiness.setText("Connect your phone over ADB to check keys, firmware, folders and games.")
    else:
        vals = (str(total), str(ready), str(building), "Linked")
        app = data.get("app") or {}
        folders = app.get("folders") or {}
        game_dir = (folders.get("game") or {}).get("path") if isinstance(folders.get("game"), dict) else None
        studio.home_readiness.setText(
            f"Keys: {'Configured' if keys else 'Missing'}   •   "
            f"Firmware: {'Configured' if firmware else 'Missing'}\n"
            f"Game folder: {game_dir or 'Not configured'}\n"
            f"GPU: {app.get('gpu_driver') or 'System'}")
    for attr, val in zip(("stat_total", "stat_ready", "stat_building", "stat_device"), vals):
        getattr(studio, attr).setText(val)
    job = normalize_job(data)
    if job:
        studio.home_build.setText(f"{job['title']}  •  {job['state']}")
        studio.home_build_detail.setText(f"{job['type']} · {job['step']} · {job['detail']}")
        studio.home_bar.setValue(job["percent"])
    else:
        studio.home_build.setText("No active Android build")
        studio.home_build_detail.setText("Your PC builder can prepare a pack, or start a build on the phone.")
        studio.home_bar.setValue(0)


def update_activity(studio, data):
    job = normalize_job(data)
    if not job:
        studio.activity_title.setText("No active Android job")
        studio.activity_state.setText("Idle")
        studio.activity_state.setObjectName("Pill")
        studio.activity_step.setText("The app reports no current Build or Prepare task.")
        studio.activity_count.setText("")
        studio.activity_error.setText("No active job diagnostics.")
        studio.activity_bar.setValue(0)
        return
    studio.activity_title.setText(job["title"])
    studio.activity_state.setText(job["state"].capitalize())
    studio.activity_state.setObjectName("Ready" if job["state"] == "done" else "Failed" if job["state"] == "failed" else "Running")
    studio.activity_state.style().unpolish(studio.activity_state)
    studio.activity_state.style().polish(studio.activity_state)
    studio.activity_step.setText(f"{job['type']} · {job['step']}\n{job['detail']}")
    studio.activity_bar.setValue(job["percent"])
    summary = []
    for step, count in job["counts"].items():
        if not isinstance(count, dict):
            continue
        done, total = count.get("done"), count.get("total")
        if done is not None and total is not None:
            summary.append(f"{step}: {done:,}/{total:,}" if isinstance(done, int) and isinstance(total, int) else f"{step}: {done}/{total}")
    if job["eta"]:
        summary.append("Android estimate: " + str(job["eta"]))
    studio.activity_count.setText("     •     ".join(summary) if summary else str(job["percent"]) + "% complete")
    details = [job["error"]] if job["error"] else []
    if job["path"]:
        details.append("Working file: " + job["path"])
    if job["log"]:
        details.append("Log: " + job["log"])
    studio.activity_error.setText("\n".join(details) or "No error reported.")


def update_library(studio, data):
    entries = library_rows(data)
    job = normalize_job(data)
    job_key = (str((data.get("job") or {}).get("title_id") or (data.get("build") or {}).get("title_id") or ""),
               job["percent"] if job else None)
    signature = (tuple((str(x.get("title_id")), str(x.get("name")), str(x.get("state")),
                        str(x.get("pack"))) for x in entries), job_key)
    if signature == getattr(studio, "_library_signature", None):
        return  # avoid rebuilding dozens of game cards on every 3.5-second status poll
    studio._library_signature = signature
    studio.game_data = entries
    total, ready, building, _, _ = readiness(data)
    studio.library_summary.setText(f"{total} games   •   {ready} ready   •   {building} building")
    render_library(studio)


def render_library(studio):
    clear_layout(studio.game_grid)
    entries = getattr(studio, "game_data", [])
    query = studio.library_find.text().strip().casefold()
    states = {1: "ready", 2: "building", 3: "build", 4: "not_in_app"}
    desired = states.get(studio.library_filter.currentIndex())
    entries = [g for g in entries if (not desired or g.get("state") == desired)
               and (not query or query in str(g.get("name", "")).casefold()
                    or query in str(g.get("title_id", "")).casefold())]
    studio.library_empty.setVisible(not entries)
    active = normalize_job(studio.latest)
    tid = str(((studio.latest.get("job") or {}).get("title_id")
               or (studio.latest.get("build") or {}).get("title_id") or "")).upper()
    for n, entry in enumerate(entries):
        percent = active["percent"] if (active and tid and tid == str(entry.get("title_id") or "").upper()) else None
        tile = GameTile(entry, studio.select_library_game, percent=percent)
        studio.game_grid.addWidget(tile, n // 3, n % 3)
    for col in range(3):
        studio.game_grid.setColumnStretch(col, 1)


def update_companions(studio, companions):
    studio.companion_data = list(companions or [])
    studio.companion_summary.setText(f"{len(studio.companion_data)} catalog entries returned by the Android app")
    render_companions(studio)


def render_companions(studio):
    clear_layout(studio.companion_grid)
    query = studio.companion_find.text().strip().casefold()
    entries = [c for c in getattr(studio, "companion_data", [])
               if isinstance(c, dict) and (not query
               or query in str(c.get("name", "")).casefold()
               or query in str(c.get("title_id", "")).casefold())]
    studio.companion_empty.setVisible(not entries)
    for n, entry in enumerate(entries):
        tid = str(entry.get("title_id") or "")
        name = str(entry.get("name") or tid)
        state = str(entry.get("state") or "none")
        version = entry.get("catalog")
        installed = entry.get("installed")
        box, v = panel(style="Tile")
        v.addWidget(textlabel(name, "TileTitle"))
        v.addWidget(subtitle("Title ID: " + tid))
        v.addWidget(subtitle(f"Catalog: {version or 'unavailable'}   •   Installed: {installed or 'no'}"))
        v.addWidget(textlabel(state.replace("_", " ").title(), "Ready" if state == "installed" else "Pill"))
        actions = QHBoxLayout()
        if entry.get("built") and state in ("not_installed", "update"):
            actions.addWidget(button("Install" if state == "not_installed" else "Update",
                                     lambda _, x=tid, op=("install" if state == "not_installed" else "update"):
                                         studio.companion_action(x, op), True))
        elif not entry.get("built"):
            actions.addWidget(subtitle("Build the game first"))
        if installed:
            actions.addWidget(button("Remove…", lambda _, x=tid: studio.companion_action(x, "remove")))
        v.addLayout(actions)
        studio.companion_grid.addWidget(box, n // 2, n % 2)
    for col in range(2):
        studio.companion_grid.setColumnStretch(col, 1)
