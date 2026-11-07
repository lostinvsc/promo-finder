"""Pick a non-overlapping shortlist and rank it (which promo to post first)."""
import math

ENTRY_BONUS = 0.10      # new viewers start at ep 1, so early-episode promos pay off with fewer spoilers
ENTRY_DECAY = 10.0
SPOILER_PENALTY = 0.06      # late-series payoffs (identity reveals, trials) spoil the show for a stranger
SPOILER_FROM, SPOILER_RAMP = 30, 15
DIVERSITY_PENALTY = 0.035   # per already-ranked promo within +-2 episodes


def overlap(a, b):
    if a.ep != b.ep:
        return 0.0
    tot = 0.0
    for s1, e1 in a.segs:
        for s2, e2 in b.segs:
            tot += max(0.0, min(e1, e2) - max(s1, s2))
    return tot / max(1e-6, min(a.duration, b.duration))


def shortlist(cands, max_total=40, per_ep=2, min_score=0.45, max_overlap=0.15):
    """Greedy non-maximum suppression: best-first, drop clips that overlap an earlier pick."""
    cands = sorted(cands, key=lambda c: -c.score)
    picked, per = [], {}
    for c in cands:
        if c.score < min_score or per.get(c.ep, 0) >= per_ep:
            continue
        if any(overlap(c, p) > max_overlap for p in picked):
            continue
        picked.append(c)
        per[c.ep] = per.get(c.ep, 0) + 1
    picked.sort(key=lambda c: -c.score)
    return picked[:max_total]


def rank(picked):
    """Re-order by score + entry-point bonus, with a diversity penalty so the first posts
    are not five clips from the same stretch of story."""
    for i, c in enumerate(sorted(picked, key=lambda c: -c.score), 1):
        c.quality_rank = i                      # pure score order, no funnel assumptions
    pool = list(picked)
    ranked = []
    while pool:
        def adj(c):
            bonus = ENTRY_BONUS * math.exp(-(c.ep - 1) / ENTRY_DECAY)
            spoil = SPOILER_PENALTY * min(1.0, max(0.0, c.ep - SPOILER_FROM) / SPOILER_RAMP)
            near = sum(1 for r in ranked if abs(r.ep - c.ep) <= 2)
            return c.score + bonus - spoil - DIVERSITY_PENALTY * near
        best = max(pool, key=adj)
        best.rank_score = round(adj(best), 4)
        ranked.append(best)
        pool.remove(best)
    return ranked
