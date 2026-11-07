"""Streamlit front-end: upload a show's screenplay .txt files (or one .zip) -> ranked promos.
Run:  streamlit run app.py      Deploy: Streamlit Community Cloud (point it at this repo, main file app.py)
Nothing is stored; uploaded scripts live in a temp folder for the session only."""
import io
import os
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from promofinder.engine import find_candidates
from promofinder.parse import load_pack
from promofinder.report import build_records
from promofinder.select import rank, shortlist

st.set_page_config(page_title="Promo Finder", layout="wide")
st.title("Promo Finder")
st.caption("Finds 20-60 s promo clips (hook -> cliffhanger -> makes sense alone) in timestamped microdrama screenplays. "
           "Heuristic engine, no API needed; optional LLM re-rank below.")

with st.sidebar:
    top = st.slider("Max promos", 10, 80, 50)
    per_ep = st.slider("Max per episode", 1, 4, 2)
    min_score = st.slider("Minimum score", 0.30, 0.80, 0.45, 0.01)
    tighten = st.checkbox("Try 2-segment cuts (slower)", value=False)
    st.markdown("**Optional LLM re-rank**")
    use_llm = st.checkbox("Re-rank shortlist with an LLM", value=False)
    provider = st.selectbox("Provider", ["openai", "anthropic"])
    base_url = st.text_input("Base URL (OpenAI-compatible, e.g. Gemini/Groq/Ollama)", "")
    model = st.text_input("Model", "gpt-4o-mini")
    key = st.text_input("API key", type="password")

files = st.file_uploader("Episode .txt files, or one .zip of them", type=["txt", "zip"], accept_multiple_files=True)

if files and st.button("Find promos", type="primary"):
    with tempfile.TemporaryDirectory() as d:
        for f in files:
            if f.name.lower().endswith(".zip"):
                zipfile.ZipFile(io.BytesIO(f.getvalue())).extractall(d)
            else:
                (Path(d) / Path(f.name).name).write_bytes(f.getvalue())
        eps = load_pack(d)
    if not eps:
        st.error("No parsable episodes found (expected 'Start: (mm:ss.xx) | End: (mm:ss.xx)' blocks).")
        st.stop()
    by = {e.num: e for e in eps}
    prog = st.progress(0.0, "Scoring candidates...")
    pool = []
    for i, ep in enumerate(eps):
        pool += find_candidates(ep, tighten_on=tighten)
        prog.progress((i + 1) / len(eps))
    if use_llm and key:
        from promofinder.llm import LLMClient, rerank
        client = LLMClient(provider, model, key, base_url or None, cache_dir=tempfile.mkdtemp())
        shortlisted = shortlist(pool, 80, 4, 0.0)
        rerank(shortlisted, by, client)
        pool = shortlisted
    recs = build_records(rank(shortlist(pool, top, per_ep, min_score)), by)
    st.session_state["recs"] = recs
    st.session_state["n_eps"] = len(eps)

recs = st.session_state.get("recs")
if recs:
    st.success(f"{len(recs)} promos from {st.session_state['n_eps']} episodes. Rank = suggested posting order.")
    df = pd.DataFrame([{
        "rank": r["rank"], "tier": r["tier"], "episode": r["episode"],
        "segments": " + ".join(f"{s['start']}-{s['end']}" for s in r["segments"]),
        "sec": r["duration_sec"], "score": r["score"], "hook": r["hook"], "cliffhanger": r["cliffhanger"],
        "why": r["why_it_works"], "flags": "; ".join(r["flags"])} for r in recs])
    st.dataframe(df, use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    c1.download_button("Download CSV", df.to_csv(index=False), "promos.csv")
    import json
    c2.download_button("Download JSON", json.dumps(recs, indent=2, ensure_ascii=False), "promos.json")
    for r in recs:
        with st.expander(f"#{r['rank']}  Ep{r['episode']}  {r['segments'][0]['start']}  ({r['duration_sec']} s, score {r['score']})"):
            st.write("**Hook:**", r["hook"])
            st.write("**Cliffhanger:**", r["cliffhanger"])
            if r["withheld_next_beat"]:
                st.write("**Withheld next beat:**", r["withheld_next_beat"])
            st.write("**Why:**", r["why_it_works"])
            if r.get("llm_reason"):
                st.write("**LLM reviewer:**", r["llm_reason"])
            st.code("\n".join(r["transcript"]), language=None)
else:
    st.info("Upload the episode files, then press **Find promos**.")
