import json
import sys

PATH = (r"c:\Users\28772\.cursor\projects\d-doctor-learning-Academic-Project-paper-1-MutaKernel"
        r"\agent-transcripts\b246ce2c-3f79-405e-88ed-baca41dee64f\subagents"
        r"\fa610df6-2423-4068-a976-5f8ba4a6b20f.jsonl")

start = int(sys.argv[1]) if len(sys.argv) > 1 else -70
lines = open(PATH, encoding="utf-8").readlines()
sel = lines[start:] if start < 0 else lines[start:start + 40]
for i, l in enumerate(sel):
    try:
        e = json.loads(l)
    except Exception:
        continue
    role = e.get("role") or e.get("type")
    m = e.get("message") or e
    c = m.get("content")
    txt = ""
    if isinstance(c, str):
        txt = c
    elif isinstance(c, list):
        parts = []
        for x in c:
            if isinstance(x, dict):
                t = x.get("text") or ""
                if t:
                    parts.append(t)
                elif x.get("name"):
                    parts.append(f"<tool:{x['name']}>")
        txt = " | ".join(parts)
    txt = txt.replace("\n", " ")
    if txt.strip():
        idx = len(lines) + start + i if start < 0 else start + i
        print(f"[{idx}] {role}: {txt[:600]}")
        print()
