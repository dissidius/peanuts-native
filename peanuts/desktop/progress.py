"""Parser for verbose native shader translation progress.

The renderer can print tens of thousands of records:
    progress 54080 73496 translate
Keep all lines for exported diagnostics, but render only milestone summaries in
the UI so a busy build doesn't dominate unrelated application pages.
"""
import re
from dataclasses import dataclass

RE_PROGRESS = re.compile(r"^\s*progress:?\s+(\d+)[ /](\d+)(?:\s+([^\r\n]+))?\s*$")

@dataclass(frozen=True)
class Progress:
    done: int
    total: int
    percent: int
    phase: str

    @property
    def text(self):
        verb = {
            "translate": "Translating shaders",
            "rewrite": "Rewriting code",
            "compile": "Compiling",
            "import": "Importing game",
        }.get(self.phase.lower(), self.phase.replace("_", " ").capitalize() if self.phase else "Processing")
        return f"{verb} · {self.done:,}/{self.total:,} ({self.percent}%)"

def parse(line):
    m = RE_PROGRESS.fullmatch(line.strip())
    if not m:
        return None
    done, total = int(m.group(1)), int(m.group(2))
    if total <= 0 or done < 0:
        return None
    return Progress(done, total, max(0, min(100, round(100 * done / total))),
                    (m.group(3) or "").strip())

class Milestones:
    def __init__(self, step=5):
        self.step = step
        self.last_phase = None
        self.last_bucket = -1

    def should_log(self, info):
        bucket = info.percent // self.step
        different = info.phase != self.last_phase
        if different or bucket > self.last_bucket or info.percent == 100 and self.last_bucket < 100 // self.step:
            self.last_phase = info.phase
            self.last_bucket = bucket
            return True
        return False
