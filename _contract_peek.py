import json
from collections import Counter
from pathlib import Path

base = Path(r"MutakernelV2\实验\补充实验数据\contracts")
print("files:", [p.name for p in base.iterdir()])
for name in ("contracts_c2c3c5_draft.jsonl",):
    rows = [json.loads(l) for l in open(base / name, encoding="utf-8")
            if l.strip()]
    print("=== %s: %d rows" % (name, len(rows)))
    r = rows[0]
    print("keys:", sorted(r.keys()))
    for k in sorted(r.keys()):
        v = str(r[k])
        print("  %s = %s" % (k, v[:160]))
    if "draft" in r:
        print("draft dist:", dict(Counter(str(x.get("draft")) for x in rows)))
