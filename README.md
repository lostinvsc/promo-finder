# Promo Finder

Finds 20-60 s promo clips (hook -> cliffhanger -> makes sense alone) in timestamped microdrama screenplays,
ranks them, and explains each pick. Rules engine by default (no API, no cost); optional LLM re-rank.
Python 3.10+, standard library only for the engine.

## Run
```bash
python run_promos.py --input <folder of episode .txt files> --out outputs     # ~25 s for 50 episodes
python evaluate.py   --input <folder> --out outputs                           # automated quality checks
streamlit run app.py                                                          # upload page (pip install -r requirements.txt)
python -m pytest -q tests                                                     # synthetic-episode tests
```
Options: `--top 50 --per-episode 2 --min-score 0.45 --tighten` (2-segment cuts, off by default).

Outputs: `promos.json` (full detail + transcript), `promos.csv` (with empty editor_verdict columns), `promos_ranked.md`.

## Optional LLM re-rank (swap the model with env vars)
```bash
export PROMO_LLM_API_KEY=...            PROMO_LLM_MODEL=gemini-2.0-flash
export PROMO_LLM_PROVIDER=openai        # openai = any OpenAI-compatible endpoint; or: anthropic
export PROMO_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai   # optional
python run_promos.py --input <folder> --out outputs --llm
```
Only the heuristic top-80 clips are sent. Run live once on `gemini-3.5-flash-lite`; failed calls keep the rules score and the run prints how many clips were scored plus the first error.

## Layout
`promofinder/parse.py` script -> events · `engine.py` candidates + scoring · `lexicon.py` all cue words (edit here to tune)
· `select.py` de-dup + posting-order rank · `report.py` hook/cliffhanger/reason · `llm.py` optional re-rank.

## Confidentiality
Do not commit the screenplay pack or its outputs (they quote it). `.gitignore` already excludes `pack/`, `data/`, `outputs/`.