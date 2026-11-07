"""Optional LLM re-ranker. OFF by default - the heuristic engine needs no API.

The model is a swappable config, not code:
  PROMO_LLM_PROVIDER = openai | anthropic        (openai = any OpenAI-compatible endpoint:
                                                  OpenAI, Gemini's /v1beta/openai, Groq, OpenRouter, Ollama...)
  PROMO_LLM_MODEL    = model id
  PROMO_LLM_API_KEY  = key
  PROMO_LLM_BASE_URL = optional, e.g. https://generativelanguage.googleapis.com/v1beta/openai
The LLM only sees the heuristic shortlist (top-K), never the whole pack, so cost stays
~K calls x ~600 input tokens per show.  Final score = (1-a)*heuristic + a*LLM (a=0.5).
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROMPT = """You are a short-drama promo editor for apps like ReelShort/DramaBox.
Below is a candidate promo clip (20-60 s) from a screenplay, in order. Judge it ONLY from the text.
Show context: {logline}

CLIP:
{clip}

Score 0-10 each:
- hook: does the first 3 seconds make a scrolling stranger stop (slap, reveal, shocking line)?
- cliffhanger: does it end on an UNRESOLVED moment that forces "what happens next"?
- standalone: does it make sense to someone who has never seen the show?
Reply with JSON only: {{"hook":n,"cliffhanger":n,"standalone":n,"reason":"one line","issues":"what is weak, or empty"}}"""


class LLMClient:
    def __init__(self, provider, model, key, base_url=None, cache_dir=".llm_cache"):
        self.provider, self.model, self.key = provider, model, key
        self.base_url = (base_url or "").rstrip("/")
        self.cache = Path(cache_dir)
        self.cache.mkdir(exist_ok=True)

    @classmethod
    def from_env(cls):
        key = os.getenv("PROMO_LLM_API_KEY")
        if not key:
            return None
        return cls(os.getenv("PROMO_LLM_PROVIDER", "openai"), os.getenv("PROMO_LLM_MODEL", "gpt-4o-mini"),
                   key, os.getenv("PROMO_LLM_BASE_URL"))

    def _post(self, url, headers, body, tries=5):
        """POST with retry/backoff on 429/500/502/503/504 (busy free-tier models)."""
        for k in range(tries):
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:300]
                if e.code in (429, 500, 502, 503, 504) and k < tries - 1:
                    time.sleep(3 * (2 ** k))
                    continue
                raise RuntimeError(f"HTTP {e.code}: {detail}")

    def complete(self, prompt):
        h = hashlib.sha1(f"{self.provider}|{self.model}|{prompt}".encode()).hexdigest()
        f = self.cache / f"{h}.txt"
        if f.exists():
            return f.read_text()
        if self.provider == "anthropic":
            d = self._post(self.base_url or "https://api.anthropic.com/v1/messages",
                           {"x-api-key": self.key, "anthropic-version": "2023-06-01",
                            "content-type": "application/json"},
                           {"model": self.model, "max_tokens": 300, "temperature": 0,
                            "messages": [{"role": "user", "content": prompt}]})
            txt = d["content"][0]["text"]
        else:
            base = self.base_url or "https://api.openai.com/v1"
            d = self._post(f"{base}/chat/completions",
                           {"Authorization": f"Bearer {self.key}", "content-type": "application/json"},
                           {"model": self.model, "temperature": 0,
                            "messages": [{"role": "user", "content": prompt}]})
            txt = d["choices"][0]["message"]["content"]
        f.write_text(txt)
        return txt


def parse_json(txt):
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        return {k: float(d[k]) for k in ("hook", "cliffhanger", "standalone")} | \
               {"reason": str(d.get("reason", "")), "issues": str(d.get("issues", ""))}
    except Exception:
        return None


def clip_text(c):
    out = []
    for x in c.events:
        if x.kind == "dialogue":
            out.append(f'{x.speaker}: "{x.text}"')
        elif x.kind in ("action", "sound"):
            out.append(f"[{x.text}]")
    return "\n".join(out)


def rerank(cands, eps_by_num, client, alpha=0.5, workers=2):
    """Adds .llm_score/.llm_reason and blends into .score. Failures fall back to heuristic
    (and are reported on stderr, never silent)."""
    errors = []

    def one(c):
        try:
            p = PROMPT.format(logline=eps_by_num[c.ep].logline, clip=clip_text(c))
            txt = client.complete(p)
            r = parse_json(txt)
            if r is None:
                errors.append("unparsable reply: " + txt[:200].replace("\n", " "))
            return r
        except Exception as e:          # network/parse problems must never kill the run
            errors.append(str(e)[:300])
            return None
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(one, cands))
    ok = sum(1 for r in res if r is not None)
    client.last_ok, client.last_total = ok, len(cands)
    client.last_error = errors[0] if errors else ""
    print(f"LLM re-rank: {ok}/{len(cands)} clips scored", file=sys.stderr)
    if errors:
        print(f"LLM errors: {len(errors)}; first: {errors[0]}", file=sys.stderr)
    for c, r in zip(cands, res):
        if r is None:
            c.llm_score = None
            continue
        c.llm_score = round((0.4 * r["hook"] + 0.4 * r["cliffhanger"] + 0.2 * r["standalone"]) / 10, 3)
        c.llm_reason = r["reason"] + (f" Issues: {r['issues']}" if r["issues"] else "")
        c.heur_score = c.score
        c.score = (1 - alpha) * c.score + alpha * c.llm_score
    return cands