"""Run: python -m pytest -q   (uses a tiny synthetic episode, not the confidential pack)"""
import sys, tempfile, zipfile, io
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from promofinder.parse import load_pack, parse_episode
from promofinder import engine as E
from promofinder.select import shortlist

def _line(speaker, s, e, text):
    return f'**{speaker}:**\nStart: ({int(s//60):02d}:{s%60:05.2f}) | End: ({int(e//60):02d}:{e%60:05.2f})\n"{text}"\n\n'

def make_episode():
    t = ["EPISODE NUMBER: Episode 1\nEPISODE LOGLINE: test\nCONTINUITY NOTES: first\n\n--- SCRIPT START ---\n\n",
         "SCENE 01\nScene heading: INT. HALL - DAY\nScene start: 00:00.00\nScene end: 00:45.00\n\nActions and dialogue:\n\n"]
    for i in range(14):
        s = i * 3.2
        t.append(f"**CAMERA:**\nStart: ({int(s//60):02d}:{s%60:05.2f}) | End: ({int((s+3.2)//60):02d}:{(s+3.2)%60:05.2f})\nClose-up.\n\n")
        who = "ANNA" if i % 2 == 0 else "BEN"
        txt = ["You lied to me!", "I am your husband.", "The truth will kill you.", "Who are you?"][i % 4]
        t.append(_line(who, s + 0.2, s + 2.8, txt))
    t.append("--- SCRIPT END ---\n")
    return "".join(t)

def test_parse_and_candidates():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "episode-001.txt").write_text(make_episode())
        eps = load_pack(d)
    assert len(eps) == 1 and eps[0].num == 1
    ev = eps[0].events
    assert sum(e.kind == "dialogue" for e in ev) == 14 and sum(e.kind == "camera" for e in ev) == 14
    c = E.find_candidates(eps[0])
    assert c, "no candidates"
    dl = [e for e in ev if e.kind == "dialogue"]
    for x in c[:50]:
        assert 20 - 0.01 <= x.duration <= 60 + 0.01
        for s, e in x.segs:
            assert not E._straddles(dl, s) and not E._straddles(dl, e)
    assert shortlist(c, 5, 2, 0.0)

def test_scoring_prefers_shock_over_filler():
    assert E.noisy_or([.5, .5]) == 0.75
    assert [k for k, _ in E.hits("He was poisoned with arsenic", E.L.SHOCK_WORDS)]

def test_zip_roundtrip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("show/episode-001.txt", make_episode())
    with tempfile.TemporaryDirectory() as d:
        zipfile.ZipFile(io.BytesIO(buf.getvalue())).extractall(d)
        assert len(load_pack(d)) == 1
