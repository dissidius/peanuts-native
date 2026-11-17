"""Live byte-weighted, non-destructive ADB transfer reporting.

ADB's LinePrinter may hide updates when stdout is not a terminal (as it is in
the Studio's QProcess). Read its progress when available, and independently
sample the *temporary* remote destination's size when it is not. No game data
is inspected or read back, and the existing atomic .tmp -> final rename stays
in push-pack.py.
"""
import json
import os
import re
import shlex
import subprocess
import threading
import time

TAG = "PEANUTS_TRANSFER\t"
ADB_PERCENT = re.compile(r"\[\s*(\d{1,3})%\]")
FIRST_NUMBER = re.compile(r"^\s*(\d+)\b")


def file_tree_bytes(path):
    """Stat, don't read, each regular file in a pack or dump tree."""
    if path.is_file():
        return path.stat().st_size
    return sum(entry.stat().st_size for entry in path.rglob("*") if entry.is_file())


class Meter:
    def __init__(self, total, output=print, clock=time.monotonic):
        self.total = max(int(total), 0)
        self.output = output
        self.clock = clock
        self.started = clock()
        self.committed = 0
        self.stage_size = 0
        self.stage_bytes = 0
        self.phase = "Preparing transfer"
        self.source = "pending"
        self.last_time = 0
        self.last_logged_bucket = -1
        self._lock = threading.Lock()

    def begin(self, label, size):
        with self._lock:
            self.phase = label
            self.stage_size = max(0, int(size))
            self.stage_bytes = 0
            self.source = "pending"
            self.last_time = 0
            self.last_logged_bucket = -1
            self._emit(force=True)

    def observe(self, bytes_done, source="device"):
        with self._lock:
            amount = min(self.stage_size, max(0, int(bytes_done)))
            if amount <= self.stage_bytes:
                return
            self.stage_bytes = amount
            self.source = source
            self._emit()

    def heartbeat(self):
        """Emit the elapsed/ETA even if adb has not supplied a percentage yet."""
        with self._lock:
            self._emit(force=True)

    def completed(self):
        with self._lock:
            self.committed = min(self.total, self.committed + self.stage_size)
            self.stage_bytes = 0
            self.stage_size = 0
            self.source = "complete"
            self._emit(force=True)

    def finish(self):
        with self._lock:
            self.committed = self.total
            self.stage_bytes = 0
            self.stage_size = 0
            self.phase = "Transfer complete"
            self.source = "complete"
            self._emit(force=True)

    def _emit(self, force=False):
        now = self.clock()
        overall = min(self.total, self.committed + self.stage_bytes)
        percent = round(100 * overall / self.total) if self.total else 100
        bucket = percent // 5
        if not force and now - self.last_time < 1 and bucket == self.last_logged_bucket:
            return
        self.last_time = now
        self.last_logged_bucket = bucket
        elapsed = max(0, now - self.started)
        rate = overall / elapsed if elapsed >= 1.0 and overall > 0 else 0
        eta = int((self.total - overall) / rate) if rate > 0 else None
        info = {"phase": self.phase, "done": overall, "total": self.total,
                "stage_done": self.stage_bytes, "stage_total": self.stage_size,
                "percent": min(100, percent), "rate": round(rate, 1),
                "eta_seconds": eta, "source": self.source}
        self.output(TAG + json.dumps(info, separators=(",", ":"), ensure_ascii=False), flush=True)


class RemoteSizeWatcher:
    """Best-effort fallback for non-interactive ADB: reads temp size only."""
    def __init__(self, serial, remote, is_dir, meter, adb_executable="adb"):
        self.stop = threading.Event()
        self.thread = threading.Thread(
            target=self._run, args=(serial, remote, is_dir, meter, adb_executable), daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=5)

    def _run(self, serial, remote, is_dir, meter, executable):
        # Do not query every 100ms; avoid slowing large ADB transfers.
        # du -sk gives allocated KiB for directories (approximate);
        # stat -c %s gives file length in bytes for a single NUP.
        cmd = "du -sk " if is_dir else "stat -c %s "
        cmd += shlex.quote(remote)
        while not self.stop.wait(2):
            meter.heartbeat()
            try:
                check = subprocess.run([executable, "-s", serial, "shell", cmd],
                    capture_output=True, text=True, timeout=3, errors="replace",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if check.returncode:
                    continue
                match = FIRST_NUMBER.match(check.stdout)
                if match:
                    meter.observe(int(match.group(1)) * (1024 if is_dir else 1),
                                  source="device" if not is_dir else "device-estimate")
            except (OSError, ValueError, subprocess.SubprocessError):
                pass


def run_adb_push(cmd, serial, remote_tmp, is_dir, meter, size):
    """Same native adb push; parse optional progress and poll temporary file."""
    print("+ " + shlex.join(cmd), flush=True)
    meter.begin("Shader pack" if is_dir and remote_tmp.endswith("android-pack.tmp")
                else "Game data" if is_dir else "Game file" if remote_tmp.endswith(".nup.tmp")
                else "Game icon", size)
    with RemoteSizeWatcher(serial, remote_tmp, is_dir, meter, cmd[0]):
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                bufsize=0, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        pending = bytearray()

        def accept(chunk):
            line = chunk.decode("utf-8", "replace").strip()
            if not line:
                return
            match = ADB_PERCENT.search(line)
            if match:
                meter.observe(int(size * min(100, int(match.group(1))) / 100), "adb")
            else:
                print(line, flush=True)

        while True:
            # Raw os.read returns currently available progress without waiting
            # for a full 4 KiB buffer (which could take an entire NUP transfer).
            chunk = os.read(proc.stdout.fileno(), 4096)
            if not chunk:
                break
            for c in chunk:
                if c == 10 or c == 13:
                    if pending:
                        accept(pending)
                        pending.clear()
                elif len(pending) < 8192:
                    pending.append(c)
        if pending:
            accept(pending)
        rc = proc.wait()
    if rc:
        raise subprocess.CalledProcessError(rc, cmd)
    meter.completed()
