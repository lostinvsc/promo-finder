"""Candidate generation + transparent heuristic scoring (no model, no API).

Pipeline per episode:
  1. cut points  : clip may start at any shot/dialogue start, end at any event end,
                   but never inside a spoken line.
  2. candidates  : every (start,end) with 20 <= len <= 60 s and >= 2 spoken lines,
                   plus 2-segment "tightened" clips (one low-value middle stretch removed)
                   for 60-90 s stretches that have a strong opening and a strong ending.
  3. features    : hook (first 3 s), cliffhanger (last ~7 s + what is withheld after the cut),
                   standalone clarity, engagement, length fit.
  4. score       : weighted GEOMETRIC mean, so a clip must be decent at ALL of hook,
                   cliffhanger and clarity - a great ending cannot rescue a dead opening.
"""
import math
import re
from dataclasses import dataclass, field

from . import lexicon as L

W_HOOK, W_CLIFF, W_CLARITY, W_ENGAGE = 0.32, 0.32, 0.20, 0.16
MIN_LEN, MAX_LEN = 20.0, 60.0
EPS = 0.04

_word_re = re.compile(r"[a-zé']+")


def noisy_or(ws):
    p = 1.0
    for w in ws:
        p *= (1.0 - min(max(w, 0.0), 0.95))
    return 1.0 - p


def hits(text, table):
    """Return [(cue, weight)] for table keys found in text (word-boundary for plain words,
    substring for multiword/stem entries)."""
    t = text.lower()
    words = set(_word_re.findall(t))
    out = []
    for k, w in table.items():
        if " " in k or not k.isalpha():
            if k in t:
                out.append((k, w))
        elif k in words:
            out.append((k, w))
        elif len(k) >= 5 and any(x.startswith(k) for x in words):   # light stemming (kill->killed)
            out.append((k, w * 0.9))
    return out


def norm_name(s):
    s = re.sub(r"^(lady|lord|the|dowager|noble|elder|blond)\s+", "", s.lower().strip())
    return s


def annotate(ep):
    """Per-event intensity in [0,1] (how scroll-stopping the beat is on its own)."""
    for ev in ep.events:
        if ev.kind == "dialogue":
            h = [w for _, w in hits(ev.text, L.SHOCK_WORDS)] + [w for _, w in hits(ev.text, L.SHOCK_PHRASES)]
            h += [w * 0.8 for _, w in hits(ev.tone, L.TONE_HOT)]
            if "!" in ev.text:
                h.append(0.18)
            if "?" in ev.text:
                h.append(0.12)
            ev.inten = noisy_or(h)
        else:
            f = 0.5 if ev.kind == "camera" else 1.0
            ev.inten = noisy_or([w * f for _, w in hits(ev.text, L.ACTION_HOT)])
    return ep


@dataclass
class Candidate:
    ep: int
    segs: list                       # [(start,end), ...] seconds in episode time
    events: list = field(default_factory=list)
    nxt: list = field(default_factory=list)       # events right after the final cut
    comp: dict = field(default_factory=dict)
    score: float = 0.0
    why: dict = field(default_factory=dict)
    kind: str = "continuous"

    @property
    def duration(self):
        return sum(e - s for s, e in self.segs)


# ------------------------------------------------------------------ candidate generation
def _straddles(dialogues, t):
    for d in dialogues:
        if d.start < t - 0.05 and d.end > t + 0.05:
            return True
    return False


def generate(ep):
    evs = ep.events
    dlg = [e for e in evs if e.kind == "dialogue"]
    starts = sorted({round(e.start, 2) for e in evs if e.kind in ("camera", "dialogue")} |
                    {round(v["start"], 2) for v in ep.scenes.values()})
    ends = sorted({round(e.end, 2) for e in evs})
    starts = [s for s in starts if not _straddles(dlg, s)]
    ends = [e for e in ends if not _straddles(dlg, e)]
    out = []
    for s in starts:
        for e in ends:
            d = e - s
            if d < MIN_LEN:
                continue
            if d > 90:
                break
            inside = [x for x in evs if x.start >= s - 0.05 and x.start < e - 0.05]
            nd = sum(1 for x in inside if x.kind == "dialogue")
            if nd < 2:
                continue
            if d <= MAX_LEN:
                out.append((s, e, "continuous", [(s, e)]))
            else:
                out.append((s, e, "raw", None))       # candidate for tightening
    return out


def tighten(ep, s, e):
    """Remove one middle stretch (<=25 s) so a 60-90 s stretch fits in 60 s.
    The removed stretch must hold no strong spoken line and sit inside one scene."""
    evs = ep.events
    dlg = [x for x in evs if x.kind == "dialogue"]
    need = (e - s) - MAX_LEN
    pts = sorted({round(x.start, 2) for x in evs if s + 8 <= x.start <= e - 12} |
                 {round(x.end, 2) for x in evs if s + 8 <= x.end <= e - 12})
    pts = [p for p in pts if not _straddles(dlg, p)]
    best = None
    for i, c1 in enumerate(pts):
        for c2 in pts[i + 1:]:
            r = c2 - c1
            if r < max(need, 6.0) - 0.01 or r > 25 or (e - s - r) < MIN_LEN:
                continue
            gap = [x for x in evs if x.kind == "dialogue" and x.start >= c1 - 0.05 and x.end <= c2 + 0.05]
            if any(g.inten > 0.30 for g in gap) or len(gap) > 3:
                continue
            sc_before = [x.scene for x in evs if x.end <= c1 + 0.05 and x.end > c1 - 3]
            sc_after = [x.scene for x in evs if x.start >= c2 - 0.05 and x.start < c2 + 3]
            if sc_before and sc_after and sc_before[-1] != sc_after[0]:
                continue
            cost = sum(g.inten for g in gap) + 0.02 * r
            if best is None or cost < best[0]:
                best = (cost, c1, c2)
    if not best:
        return None
    return [(s, best[1]), (best[2], e)]


# ------------------------------------------------------------------ scoring
def _view(ep, segs):
    """Flatten segments into clip-time events: [(ev, ct_start, ct_end)]."""
    out, off = [], 0.0
    for s, e in segs:
        for x in ep.events:
            if x.start >= s - 0.05 and x.start < e - 0.05:
                a = off + (x.start - s)
                b = off + (min(x.end, e) - s)
                out.append((x, a, b))
        off += e - s
    return out, off


def score(ep, cand):
    view, dur = _view(ep, cand.segs)
    cand.events = [v[0] for v in view]
    last_end = cand.segs[-1][1]
    cand.nxt = [x for x in ep.events if x.start >= last_end - 0.05 and x.start < last_end + 10 and x.kind != "camera"]
    why = {}

    # ---- HOOK : first 3 seconds -------------------------------------------------
    first = [(x, a, b) for x, a, b in view if a < 3.0]
    fd = [t for t in first if t[0].kind == "dialogue"]
    fa = [t for t in first if t[0].kind != "dialogue"]
    d_int, hook_ev = 0.0, None
    if fd:
        x = max(fd, key=lambda t: t[0].inten)[0]
        d_int = x.inten
        nwords = len(x.text.split())
        if nwords <= 9:
            d_int = noisy_or([d_int, 0.12])
        if re.match(r"\s*(you|your|how dare|who|what|why)\b", x.text, re.I) and (x.text.endswith(("!", "?"))):
            d_int = noisy_or([d_int, 0.12])
        hook_ev = x
        why["hook_words"] = [k for k, _ in hits(x.text, L.SHOCK_WORDS) + hits(x.text, L.SHOCK_PHRASES)][:4]
    a_int = 0.0
    if fa:
        t = max(fa, key=lambda t: t[0].inten)
        a_int = t[0].inten
        if hook_ev is None or (a_int > d_int + 0.15 and t[0].kind != "camera"):
            hook_ev = t[0] if a_int > 0.25 else hook_ev
        why["hook_action"] = [k for k, _ in hits(t[0].text, L.ACTION_HOT)][:3]
    hook = noisy_or([d_int, a_int * 0.85])
    if fd and fd[0][1] <= 1.5:
        hook = noisy_or([hook, 0.08])
    pen = 1.0
    fx = fd[0][0] if fd else None
    if fx is not None:
        low = fx.text.lower().strip()
        w0 = _word_re.findall(low)
        if any(low.startswith(g) for g in L.GREETING):
            pen *= 0.7; why.setdefault("flags", []).append("greeting opener")
        if w0 and (w0[0] in L.RESPONSE_OPEN) and len(w0) <= 5:
            pen *= 0.8; why.setdefault("flags", []).append("reply-to-nothing opener")
        elif w0 and w0[0] in L.PRONOUN_OPEN:
            pen *= 0.88; why.setdefault("flags", []).append("opens mid-thought")
    if not fd and a_int < 0.3:
        pen *= 0.6; why.setdefault("flags", []).append("quiet/establishing opening")
    hook = min(1.0, hook * pen)

    # ---- CLIFFHANGER : last ~7 s + what is withheld ---------------------------------
    tail = [(x, a, b) for x, a, b in view if b > dur - 7.0]
    tail_text = " ".join(x.text for x, _, _ in tail if x.kind != "dialogue")
    cue = noisy_or([w for _, w in hits(tail_text, L.CLIFF_CUES)])
    last_d = None
    for x, a, b in reversed(view):
        if x.kind == "dialogue":
            last_d = (x, a, b); break
    line_c = 0.0
    if last_d and last_d[2] > dur - 8:
        x = last_d[0]
        lw = [w for k, w in L.CLIFF_LINE_CUES.items() if (k in x.text.lower()) and (k in "?!...—--" or len(k) > 1)]
        lw = [w for k, w in L.CLIFF_LINE_CUES.items() if k in x.text.lower()]
        line_c = noisy_or(lw + [x.inten * 0.9] + [w * 0.8 for _, w in hits(x.tone, L.TONE_HOT)])
    nxt_int = max([x.inten for x in cand.nxt[:4]] + [0.0])
    at_ep_end = last_end >= ep.duration - 0.6
    cliff = noisy_or([cue, line_c * 0.9, nxt_int * 0.55 if not at_ep_end else 0.0])
    res = noisy_or([w for _, w in hits(" ".join(x.text for x, _, _ in tail), L.RESOLVED_CUES)])
    cliff *= (1.0 - 0.7 * res)
    if at_ep_end and cliff >= 0.3:
        cliff = noisy_or([cliff, 0.08])
    why["cliff_cues"] = [k for k, _ in hits(tail_text, L.CLIFF_CUES)][:4]
    why["resolved_cues"] = [k for k, _ in hits(" ".join(x.text for x, _, _ in tail), L.RESOLVED_CUES)][:3]
    why["next_int"] = round(nxt_int, 2)
    why["episode_end"] = at_ep_end

    # ---- CLARITY : standalone sense ---------------------------------------------------
    dls = [x for x, _, _ in view if x.kind == "dialogue"]
    spk = {norm_name(x.speaker) for x in dls}
    n = len(spk)
    sp = {1: 0.35, 2: 1.0, 3: 0.9, 4: 0.6}.get(n, 0.3)
    rel_words = sorted({w for x in dls for w in _word_re.findall(x.text.lower()) if w in L.RELATION_WORDS})
    rel = min(1.0, len(rel_words) / 3.0)
    dl = min(1.0, len(dls) / 6.0)
    scenes = {x.scene for x, _, _ in view}
    sc_pen = min(0.3, 0.12 * (len(scenes) - 1))
    clar = 0.40 * sp + 0.25 * rel + 0.35 * dl - sc_pen
    if "picks up" in ep.continuity.lower() or "continues" in ep.continuity.lower():
        if cand.segs[0][0] < 10:
            clar -= 0.08; why.setdefault("flags", []).append("depends on previous episode")
    if fx is not None and any(f in why.get("flags", []) for f in ("reply-to-nothing opener", "opens mid-thought")):
        clar -= 0.12
    clar = min(1.0, max(0.0, clar))
    why["speakers"] = sorted(s.title() for s in spk)
    why["relation_words"] = rel_words[:5]
    why["scene_changes"] = len(scenes) - 1

    # ---- ENGAGEMENT -----------------------------------------------------------------
    ints = sorted((x.inten for x, _, _ in view if x.kind in ("dialogue", "action")), reverse=True)
    top = sum(ints[:5]) / max(1, len(ints[:5]))
    half = dur / 2
    a1 = [x.inten for x, a, _ in view if a < half and x.kind == "dialogue"]
    a2 = [x.inten for x, a, _ in view if a >= half and x.kind == "dialogue"]
    esc = (sum(a2) / len(a2) if a2 else 0) - (sum(a1) / len(a1) if a1 else 0)
    esc = min(1.0, max(0.0, esc) / 0.3)
    words = sum(len(x.text.split()) for x in dls)
    wps = words / dur
    dens = max(0.0, 1.0 - abs(wps - 2.4) / 2.0)
    eng = 0.5 * top + 0.2 * esc + 0.3 * dens

    # ---- LENGTH ------------------------------------------------------------------------
    if 28 <= dur <= 50:
        P = 1.0
    elif dur < 28:
        P = 0.75 + 0.25 * (dur - 20) / 8
    else:
        P = 1.0 - 0.15 * (dur - 50) / 10
    if cand.kind == "tightened":
        P *= 0.96

    comp = {"hook": hook, "cliffhanger": cliff, "clarity": clar, "engagement": eng, "length_fit": P}
    g = (W_HOOK * math.log(max(hook, EPS)) + W_CLIFF * math.log(max(cliff, EPS)) +
         W_CLARITY * math.log(max(clar, EPS)) + W_ENGAGE * math.log(max(eng, EPS)))
    cand.score = math.exp(g) * (P ** 0.5)
    cand.comp = {k: round(v, 3) for k, v in comp.items()}
    cand.why = why
    cand.hook_ev = hook_ev
    cand.last_dialogue = last_d[0] if last_d else None
    cand.tail_events = [x for x, _, _ in tail if x.kind != "dialogue"]
    return cand


def find_candidates(ep, keep_per_ep=400, tighten_on=False):
    """Generate + score; returns scored candidates (best first)."""
    annotate(ep)
    raw = generate(ep)
    cands = []
    # first pass: continuous
    for s, e, kind, segs in raw:
        if kind == "continuous":
            c = Candidate(ep.num, segs)
            cands.append(score(ep, c))
    # second pass: tighten only promising 60-90 s stretches
    cont_by_start = {}
    for c in cands:
        cont_by_start.setdefault(round(c.segs[0][0], 2), []).append(c.comp["hook"])
    for s, e, kind, _ in raw:
        if kind != "raw" or not tighten_on:
            continue
        segs = tighten(ep, s, e)
        if not segs:
            continue
        c = Candidate(ep.num, segs, kind="tightened")
        score(ep, c)
        if c.comp["hook"] >= 0.35 and c.comp["cliffhanger"] >= 0.35:
            cands.append(c)
    cands.sort(key=lambda c: -c.score)
    return cands[:keep_per_ep]
