import json

base = r"MutakernelV2\实验\补充实验数据\collection_frames"
for name in ("C3_subject_frame.jsonl", "C5_collection_frame.jsonl",
             "C3_collection_frame.jsonl"):
    p = base + "\\" + name
    try:
        rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    except FileNotFoundError:
        print("=== %s: MISSING" % name)
        continue
    print("=== %s: %d rows" % (name, len(rows)))
    r = rows[0]
    print("keys:", sorted(r.keys()))
    for k in sorted(r.keys()):
        print("  %s = %s" % (k, str(r[k])[:110]))
    # status field distribution
    for k in ("status", "included", "accepted", "language", "level"):
        if k in r:
            from collections import Counter
            print("  dist[%s]:" % k,
                  dict(Counter(str(x.get(k)) for x in rows)))
