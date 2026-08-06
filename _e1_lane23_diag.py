import _remote

DIAG = r"""
import json
from collections import Counter

for lane in (2, 3):
    path = f"/root/mk_v2_runs/e1/equiv_observations_lane{lane}.jsonl"
    recs = [json.loads(l) for l in open(path) if l.strip()]
    inc = [r for r in recs if r.get("evidence_grade") == "INCONCLUSIVE"]
    print(f"=== lane{lane}: total={len(recs)} inconclusive={len(inc)} ===")
    print(" class:", dict(Counter(r.get("inconclusive_class") for r in inc)))
    print(" timed_out:", sum(1 for r in inc if r.get("timed_out")))
    walls = sorted(r.get("wall_ms", 0) for r in inc)
    if walls:
        print(f" wall_s median={walls[len(walls)//2]/1000:.0f} max={walls[-1]/1000:.0f}")
    kc = Counter(r.get("kernel") for r in inc)
    print(" kernels:", dict(kc.most_common(8)))
    rounds = Counter()
    for r in inc:
        tr = r.get("trials") or []
        nrand = sum(1 for t in tr if t.get("round_type") == "random")
        nstr = sum(1 for t in tr if t.get("round_type") == "stress")
        rounds[(nrand, nstr)] += 1
    print(" completed (random,stress) rounds:", dict(rounds.most_common(8)))
    reasons = Counter()
    for r in inc[:200]:
        for t in (r.get("trials") or []):
            if t.get("status") == "inconclusive":
                reasons[(t.get("reason") or "")[:70]] += 1
    print(" trial-level inconclusive reasons:", dict(reasons.most_common(6)))
    ok = [r for r in recs if r.get("evidence_grade") == "LIKELY_EQUIVALENT"]
    bex = sum(1 for r in ok if (r.get("evidence") or {}).get("budget_exhausted"))
    print(f" LIKELY with budget_exhausted: {bex}/{len(ok)}")
print("DIAG23_DONE")
"""

c = _remote.connect()
s = c.open_sftp()
with s.open("/root/mk_v2/_diag23.py", "w") as f:
    f.write(DIAG)
s.close()
_, out, _ = _remote.run(c, "/root/miniconda3/bin/python /root/mk_v2/_diag23.py 2>&1",
                        timeout=180, echo=False)
c.close()
print(out)
