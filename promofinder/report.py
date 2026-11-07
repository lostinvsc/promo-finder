"""Turn ranked candidates into JSON / CSV / Markdown output with hook, cliffhanger, reason."""
import csv
import json
from pathlib import Path

from .parse import sec_to_ts


def _q(ev, n=140):
    t = ev.text.strip()
    t = t if len(t) <= n else t[: n - 1] + "…"
    return f'{ev.speaker}: "{t}"' if ev.kind == "dialogue" else t


def describe(cand, ep):
    """Template-based hook / cliffhanger / reason, built only from the script text."""
    w = cand.why
    s0 = cand.segs[0][0]
    # hook
    h = cand.hook_ev
    if h is None:
        hook = "No strong opening beat found (see flags)."
        h_ts = sec_to_ts(s0)
    else:
        h_ts = sec_to_ts(h.start)
        hook = f"[{h_ts}] {_q(h)}"
    # cliffhanger: final spoken line + final non-speech beat + what is withheld
    parts = []
    if cand.last_dialogue is not None and cand.last_dialogue.end > cand.segs[-1][1] - 8:
        parts.append(_q(cand.last_dialogue))
    if cand.tail_events:
        te = max(cand.tail_events, key=lambda x: (x.kind == "action", x.kind == "sound", x.inten, x.start))
        parts.append(te.text if len(te.text) < 170 else te.text[:169] + "…")
    cliff = " | ".join(parts) if parts else "Ends on a held shot."
    withheld = ""
    if cand.nxt:
        withheld = _q(max(cand.nxt[:3], key=lambda x: x.inten), 110)
    # reason
    bits = []
    if w.get("hook_words") or w.get("hook_action"):
        cues = (w.get("hook_words") or []) + (w.get("hook_action") or [])
        bits.append(f"opens on a charged beat ({', '.join(cues[:3])})")
    elif h is not None:
        bits.append("opens straight into a line of dialogue")
    if w.get("cliff_cues") or cand.comp["cliffhanger"] >= 0.5:
        why_c = w.get("cliff_cues") or []
        bits.append("cuts at an unresolved beat" + (f" ({', '.join(why_c[:2])})" if why_c else ""))
    if w.get("next_int", 0) >= 0.4 and not w.get("episode_end"):
        bits.append("the very next beat is withheld")
    if w.get("episode_end"):
        bits.append("lands on the episode-ending beat")
    sp = w.get("speakers", [])
    bits.append(f"{len(sp)} speaker{'s' if len(sp) != 1 else ''} in {'one scene' if w.get('scene_changes', 0) == 0 else 'a scene change'}"
                + (f", relationships clear ({', '.join(w['relation_words'][:3])})" if w.get("relation_words") else ""))
    reason = "; ".join(bits).capitalize() + "."
    return hook, cliff, withheld, reason


def transcript(cand):
    lines = []
    for x in cand.events:
        if x.kind == "dialogue":
            lines.append(f'{x.speaker}: "{x.text}"')
        elif x.kind in ("action", "sound"):
            lines.append(f"[{x.kind}] {x.text}")
    return lines


def build_records(ranked, eps_by_num):
    recs = []
    for i, c in enumerate(ranked, 1):
        ep = eps_by_num[c.ep]
        hook, cliff, withheld, reason = describe(c, ep)
        flags = list(c.why.get("flags", []))
        if c.kind == "tightened":
            flags.append("2-segment cut (middle stretch removed)")
        if c.comp["hook"] < 0.45:
            flags.append("weak hook - editor should check the first 3s")
        if c.comp["cliffhanger"] < 0.45:
            flags.append("weak cliffhanger - check the ending")
        recs.append({
            "rank": i,
            "tier": "A - post first" if i <= 10 else ("B - second wave" if i <= 25 else "C - backlog"),
            "quality_rank": getattr(c, "quality_rank", i),
            "promo_id": f"E{c.ep:03d}-{int(c.segs[0][0]*100):05d}",
            "episode": c.ep,
            "segments": [{"episode": c.ep, "start": sec_to_ts(a), "end": sec_to_ts(b),
                          "start_sec": round(a, 2), "end_sec": round(b, 2)} for a, b in c.segs],
            "duration_sec": round(c.duration, 1),
            "score": round(c.score, 3),
            "rank_score": getattr(c, "rank_score", None),
            "llm_score": getattr(c, "llm_score", None),
            "components": c.comp,
            "hook": hook,
            "cliffhanger": cliff,
            "withheld_next_beat": withheld,
            "why_it_works": reason,
            "llm_reason": getattr(c, "llm_reason", None),
            "flags": flags,
            "episode_logline": ep.logline,
            "transcript": transcript(c),
        })
    return recs


def write_all(recs, outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "promos.json").write_text(json.dumps(recs, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(out / "promos.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "tier", "quality_rank", "promo_id", "episode", "segments (start-end)", "duration_s", "score",
                    "hook", "cliffhanger", "why_it_works", "flags", "editor_verdict (good/ok/bad)", "editor_note"])
        for r in recs:
            segs = " + ".join(f"{s['start']}-{s['end']}" for s in r["segments"])
            w.writerow([r["rank"], r["tier"], r["quality_rank"], r["promo_id"], r["episode"], segs, r["duration_sec"], r["score"],
                        r["hook"], r["cliffhanger"], r["why_it_works"], "; ".join(r["flags"]), "", ""])
    md = ["# Ranked promos\n"]
    for r in recs:
        segs = " + ".join(f"Ep{r['episode']} {s['start']}–{s['end']}" for s in r["segments"])
        c = r["components"]
        md.append(f"## #{r['rank']}  {segs}  ({r['duration_sec']} s, score {r['score']}, quality-rank {r['quality_rank']}, tier {r['tier']})")
        md.append(f"- **Hook:** {r['hook']}")
        md.append(f"- **Cliffhanger:** {r['cliffhanger']}")
        if r["withheld_next_beat"]:
            md.append(f"- **Withheld (what comes right after the cut):** {r['withheld_next_beat']}")
        md.append(f"- **Why it works:** {r['why_it_works']}")
        if r.get("llm_reason"):
            md.append(f"- **LLM reviewer:** {r['llm_reason']}")
        md.append(f"- Scores: hook {c['hook']} · cliffhanger {c['cliffhanger']} · clarity {c['clarity']} · "
                  f"engagement {c['engagement']} · length {c['length_fit']}")
        if r["flags"]:
            md.append(f"- ⚠ Flags: {'; '.join(r['flags'])}")
        md.append("")
    (out / "promos_ranked.md").write_text("\n".join(md), encoding="utf-8")
