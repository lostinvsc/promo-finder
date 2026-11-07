#!/usr/bin/env python3
"""Quality checks that need no labels and no API. Writes <out>/quality_report.md + .json.

1. validity   - hard rules on every returned promo (length, no cut inside a spoken line, ...)
2. baselines  - picks vs. 'last 45 s of each episode', 'first 45 s', and random valid windows
                (SELF-SCORED: shows the engine separates, it does NOT prove editors agree)
3. stability  - jitter every weight +-30 % x 30 trials, how much of the top-20 survives
4. ablation   - drop one component at a time: what does each one actually drive?
5. coverage   - which episodes yield nothing, and why
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from promofinder import engine as E                      # noqa: E402
from promofinder.parse import load_pack                  # noqa: E402
from promofinder.select import rank, shortlist           # noqa: E402

BASE_W = {"hook": E.W_HOOK, "cliffhanger": E.W_CLIFF, "clarity": E.W_CLARITY, "engagement": E.W_ENGAGE}


def rescore(c, w):
    tot = sum(w.values()) or 1.0
    g = sum((w[k] / tot) * math.log(max(c.comp[k], E.EPS)) for k in w)
    return math.exp(g) * (c.comp["length_fit"] ** 0.5)


def top_ids(pool, w, n=20):
    for c in pool:
        c.score = rescore(c, w)
    return shortlist(pool, n, 2, 0.0)


def agree(a, b):
    """share of clips in a that have a clip in b covering the same moment (same episode, >=30 % overlap)"""
    from promofinder.select import overlap
    return sum(1 for x in a if any(overlap(x, y) >= 0.3 for y in b)) / len(a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default="outputs")
    a = ap.parse_args()
    eps = load_pack(a.input)
    by = {e.num: e for e in eps}
    pool = []
    for ep in eps:
        pool += E.find_candidates(ep)
    for c in pool:
        c._orig = c.score
    picked = shortlist(pool, 50, 2, 0.45)
    rep = {}

    # 1 validity ------------------------------------------------------------------------
    bad = []
    for c in picked:
        ep = by[c.ep]
        dl = [x for x in ep.events if x.kind == "dialogue"]
        for s, e in c.segs:
            if E._straddles(dl, s) or E._straddles(dl, e):
                bad.append((c.ep, s, e, "cut inside spoken line"))
        if not (E.MIN_LEN - 0.01 <= c.duration <= E.MAX_LEN + 0.01):
            bad.append((c.ep, c.segs, "length"))
        if sum(1 for x in c.events if x.kind == "dialogue") < 2:
            bad.append((c.ep, c.segs, "<2 spoken lines"))
    rep["validity"] = {"promos": len(picked), "violations": len(bad), "detail": bad[:5],
                       "tightened_clips": sum(1 for c in picked if c.kind == "tightened"),
                       "median_len_s": round(sorted(c.duration for c in picked)[len(picked) // 2], 1)}

    # 2 baselines -----------------------------------------------------------------------
    rnd = random.Random(7)
    base = {"last_45s": [], "first_45s": [], "random_valid": []}
    for ep in eps:
        E.annotate(ep)
        raw = [r for r in E.generate(ep) if r[2] == "continuous"]
        if not raw:
            continue
        last = min(raw, key=lambda r: (abs(r[1] - ep.duration) > 0.6, abs((r[1] - r[0]) - 45)))
        first = min(raw, key=lambda r: (abs(r[0]), abs((r[1] - r[0]) - 45)))
        for name, rr in (("last_45s", [last]), ("first_45s", [first]), ("random_valid", rnd.sample(raw, min(3, len(raw))))):
            for r in rr:
                base[name].append(E.score(ep, E.Candidate(ep.num, r[3])))

    def agg(cs):
        n = len(cs)
        m = lambda f: round(sum(f(c) for c in cs) / n, 3)
        return {"n": n, "score": m(lambda c: c._orig if hasattr(c, "_orig") else c.score),
                **{k: m(lambda c, k=k: c.comp[k]) for k in ("hook", "cliffhanger", "clarity", "engagement")}}
    rep["baselines"] = {"engine_picks": agg(picked), **{k: agg(v) for k, v in base.items()}}

    # 3 stability -----------------------------------------------------------------------
    for c in pool:
        c.score = c._orig
    ref = top_ids(pool, BASE_W)
    rnd = random.Random(11)
    j = []
    for _ in range(30):
        w = {k: v * rnd.uniform(0.7, 1.3) for k, v in BASE_W.items()}
        t = top_ids(pool, w)
        j.append(agree(ref, t))
    rep["stability_top20_overlap"] = {"mean": round(sum(j) / len(j), 2), "min": round(min(j), 2)}

    # 4 ablation ------------------------------------------------------------------------
    abl = {}
    for k in BASE_W:
        w = dict(BASE_W); w[k] = 0.0
        abl[f"drop_{k}"] = round(agree(ref, top_ids(pool, w)), 2)
    rep["ablation_top20_overlap"] = abl

    # 4b tightened (2-segment) experiment -----------------------------------------------
    tp = []
    for ep in eps:
        tp += [c for c in E.find_candidates(ep, tighten_on=True) if c.kind == "tightened"]
    cut50 = picked[-1].score
    rep["tightened_experiment"] = {"candidates": len(tp), "best_score": round(max((c.score for c in tp), default=0), 3),
                                   "score_of_50th_continuous_pick": round(cut50, 3),
                                   "beat_50th": sum(1 for c in tp if c.score > cut50),
                                   "survive_dedup_in_top50": sum(1 for c in shortlist(pool + tp, 50, 2, 0.45) if c.kind == "tightened")}

    # 5 coverage ------------------------------------------------------------------------
    for c in pool:
        c.score = c._orig
    got = {c.ep for c in picked}
    best = {}
    for c in pool:
        best[c.ep] = max(best.get(c.ep, 0), c.score)
    rep["coverage"] = {"episodes_with_a_promo": len(got), "episodes_without": sorted(set(by) - got),
                       "best_score_in_unpicked_eps": {str(k): round(best[k], 2) for k in sorted(set(by) - got)}}

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "quality_report.json").write_text(json.dumps(rep, indent=2))
    b = rep["baselines"]
    md = ["# Automated quality checks\n", "_No labels, no API. Baseline scores are self-scored by the same engine, "
          "so they show separation, not editor agreement._\n",
          "## 1. Validity", f"- {rep['validity']['promos']} promos, **{rep['validity']['violations']} rule violations** "
          f"(length 20-60 s, no cut inside a spoken line, >=2 lines). Median length {rep['validity']['median_len_s']} s; "
          f"{rep['validity']['tightened_clips']} are 2-segment tightened cuts.",
          "\n## 2. Picks vs. naive baselines (mean per clip)", "| set | n | score | hook | cliffhanger | clarity | engagement |", "|---|---|---|---|---|---|---|"]
    for k, v in b.items():
        md.append(f"| {k} | {v['n']} | {v['score']} | {v['hook']} | {v['cliffhanger']} | {v['clarity']} | {v['engagement']} |")
    md += ["\n## 3. Stability (weights jittered +-30 %, 30 trials)",
           f"- share of base top-20 moments still picked (same episode, >=30 % time overlap): mean {rep['stability_top20_overlap']['mean']}, worst {rep['stability_top20_overlap']['min']}",
           "\n## 4. Ablation (share of base top-20 moments still picked when one component is removed)"]
    md += [f"- {k}: {v}" for k, v in abl.items()]
    t = rep["tightened_experiment"]
    md += [f"\n## 4b. 2-segment 'tightened' cuts (--tighten)", f"- {t['candidates']} candidates; best {t['best_score']} vs 50th continuous pick {t['score_of_50th_continuous_pick']}; {t['beat_50th']} outscore the 50th pick, but {t['survive_dedup_in_top50']} survive de-duplication (each overlaps an equal-or-better single-segment clip of the same scene, or hits the 2-per-episode cap)"]
    md += ["\n## 5. Coverage", f"- {rep['coverage']['episodes_with_a_promo']}/50 episodes yield a promo; none from: {rep['coverage']['episodes_without']}"]
    (out / "quality_report.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
