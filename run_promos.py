#!/usr/bin/env python3
"""Find promos in a folder of timestamped screenplays.

  python run_promos.py --input <folder with episode .txt files> --out outputs
  python run_promos.py --input pack --out outputs --llm      # optional re-rank (needs PROMO_LLM_API_KEY)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from promofinder.engine import find_candidates          # noqa: E402
from promofinder.parse import load_pack                  # noqa: E402
from promofinder.report import build_records, write_all  # noqa: E402
from promofinder.select import rank, shortlist           # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default="outputs")
    ap.add_argument("--top", type=int, default=50, help="max promos to return")
    ap.add_argument("--per-episode", type=int, default=2)
    ap.add_argument("--min-score", type=float, default=0.45)
    ap.add_argument("--tighten", action="store_true", help="also try 2-segment cuts that drop a filler stretch (slower; never won on the test show)")
    ap.add_argument("--llm", action="store_true", help="re-rank the shortlist with an LLM (optional)")
    ap.add_argument("--llm-topk", type=int, default=80)
    a = ap.parse_args()

    eps = load_pack(a.input)
    if not eps:
        sys.exit(f"No parsable episodes under {a.input}")
    by_num = {e.num: e for e in eps}
    pool = []
    for ep in eps:
        pool += find_candidates(ep, tighten_on=a.tighten)
    print(f"{len(eps)} episodes, {sum(len(e.events) for e in eps)} events, {len(pool)} scored candidates")

    if a.llm:
        from promofinder.llm import LLMClient, rerank
        client = LLMClient.from_env()
        if client is None:
            sys.exit("--llm needs PROMO_LLM_API_KEY (and optionally PROMO_LLM_PROVIDER/MODEL/BASE_URL)")
        top = shortlist(pool, max_total=a.llm_topk, per_ep=4, min_score=0.0)
        rerank(top, by_num, client)
        pool = top

    picked = shortlist(pool, a.top, a.per_episode, a.min_score)
    ranked = rank(picked)
    recs = build_records(ranked, by_num)
    write_all(recs, a.out)
    print(f"wrote {len(recs)} promos -> {a.out}/promos.json, promos.csv, promos_ranked.md")


if __name__ == "__main__":
    main()
