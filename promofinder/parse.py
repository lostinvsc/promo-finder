"""Parse Kuku-style timestamped screenplays into typed events.

Format (per episode .txt):
  EPISODE NUMBER / LOGLINE / CONTINUITY NOTES header, then
  SCENE NN / heading / scene start / scene end, then blocks:
    **LABEL (tone):**
    Start: (mm:ss.xx) | End: (mm:ss.xx)
    text...
Labels CAMERA / ACTION / SOUND FX are non-speech; anything else is a speaker.
Header keys differ in case between episodes ("Scene start" vs "SCENE START"),
so everything is matched case-insensitively.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

TS = r"\(?(\d+):(\d+(?:\.\d+)?)\)?"
RE_TIME = re.compile(rf"Start:\s*{TS}\s*\|\s*End:\s*{TS}", re.I)
RE_BLOCK = re.compile(r"^\*\*(.+?):\*\*\s*$")
RE_SCENE = re.compile(r"^SCENE\s+(\d+)\s*$", re.I)
RE_SCENE_KV = re.compile(r"^(scene heading|scene start|scene end)\s*:\s*(.*)$", re.I)
NONSPEECH = {"CAMERA": "camera", "ACTION": "action", "SOUND FX": "sound"}


def ts_to_sec(m, s):
    return int(m) * 60 + float(s)


def sec_to_ts(t):
    t = max(0.0, t)
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


@dataclass
class Event:
    ep: int
    scene: int
    kind: str            # camera | action | sound | dialogue
    speaker: str
    tone: str
    text: str
    start: float
    end: float
    idx: int = 0


@dataclass
class Episode:
    num: int
    logline: str
    continuity: str
    events: list = field(default_factory=list)
    scenes: dict = field(default_factory=dict)   # scene no -> (heading, start, end)
    duration: float = 0.0
    path: str = ""


def parse_episode(path):
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    ep = Episode(num=0, logline="", continuity="", path=str(path))
    scene = 0
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i].strip()
        if ln.upper().startswith("EPISODE NUMBER"):
            m = re.search(r"(\d+)", ln)
            ep.num = int(m.group(1)) if m else 0
        elif ln.upper().startswith("EPISODE LOGLINE"):
            ep.logline = ln.split(":", 1)[1].strip()
        elif ln.upper().startswith("CONTINUITY NOTES"):
            ep.continuity = ln.split(":", 1)[1].strip()
        elif RE_SCENE.match(ln):
            scene = int(RE_SCENE.match(ln).group(1))
            ep.scenes[scene] = {"heading": "", "start": 0.0, "end": 0.0}
        elif RE_SCENE_KV.match(ln) and scene:
            k, v = RE_SCENE_KV.match(ln).groups()
            k = k.lower()
            if k == "scene heading":
                ep.scenes[scene]["heading"] = v.strip()
            else:
                mm = re.search(r"(\d+):(\d+(?:\.\d+)?)", v)
                if mm:
                    ep.scenes[scene]["start" if k == "scene start" else "end"] = ts_to_sec(*mm.groups())
        elif RE_BLOCK.match(ln):
            label = RE_BLOCK.match(ln).group(1).strip()
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            tm = RE_TIME.search(lines[j]) if j < n else None
            if tm:
                s = ts_to_sec(tm.group(1), tm.group(2))
                e = ts_to_sec(tm.group(3), tm.group(4))
                body = []
                j += 1
                while j < n and lines[j].strip() and not RE_BLOCK.match(lines[j].strip()) \
                        and not lines[j].strip().startswith("--- SCRIPT"):
                    body.append(lines[j].strip())
                    j += 1
                base = re.sub(r"\s*\(.*\)\s*$", "", label).strip()
                tone = ""
                mt = re.search(r"\((.*)\)\s*$", label)
                if mt:
                    tone = mt.group(1)
                kind = NONSPEECH.get(base.upper(), "dialogue")
                text = " ".join(body).strip()
                if kind == "dialogue":
                    text = text.strip('"“”')
                ep.events.append(Event(ep.num, scene, kind, "" if kind != "dialogue" else base.title().replace("'S","'s"),
                                       tone, text, s, e))
                i = j - 1
        i += 1
    ep.events.sort(key=lambda ev: (ev.start, ev.end))
    for k, ev in enumerate(ep.events):
        ev.idx = k
    ep.duration = max([e.end for e in ep.events] + [0.0])
    return ep


def load_pack(folder):
    files = sorted(Path(folder).rglob("*.txt"))
    eps = [parse_episode(f) for f in files]
    eps = [e for e in eps if e.events]
    eps.sort(key=lambda e: e.num)
    return eps
