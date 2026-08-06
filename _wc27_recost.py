import _remote
c = _remote.connect()
R = _remote.run
script = r'''
import json, collections
E1 = "/root/mk_v2_runs/e1"
STARTUP = 70.0
inv = json.load(open(E1 + "/_wc_witness_inventory.json"))
kernels = sorted({r["kernel"] for r in inv})
eq = [json.loads(l) for l in open(E1 + "/equiv_observations.jsonl") if l.strip()]
per = collections.defaultdict(list)
for r in eq:
    k = r.get("kernel")
    tr = r.get("trials") or []
    w = r.get("wall_ms")
    if k in kernels and tr and w:
        c = (w / 1000.0 - STARTUP) / len(tr)
        if c > 0:
            per[k].append(c)
out = {}
print("kernel   corrected s/round (median)   n")
for k in kernels:
    v = sorted(per[k])
    m = v[len(v)//2] if v else 0.5
    out[k] = round(m, 3)
    print("  %-8s %7.2f   n=%d" % (k, m, len(v)))
json.dump(out, open(E1 + "/_wc_round_wall.json", "w"), indent=1)

# validate against the 8 cells already executed
import glob, os
print("\nvalidation vs executed cells:")
for p in sorted(glob.glob(E1 + "/witness_confirmation/cells/*.json")):
    r = json.load(open(p))
    n = len(r["rounds"])
    if n:
        print("  %-42s rounds=%-4d wall=%6.1f  implied=%5.2f s/round  model=%5.2f"
              % (r["cell_id"], n, r["wall_s"], (r["wall_s"] - STARTUP) / n,
                 out.get(r["kernel"], 0.5)))

def cost(n_a, n_b):
    proto = {"equiv": 20, "cse": 40}
    ctot = 0
    detail = []
    bykey = collections.defaultdict(lambda: {"pol": set(), "maxsi": 0, "rand": []})
    for rec in inv:
        d = rec.get("divergence") or {}
        if d.get("round_type") == "stress":
            e = bykey[(rec["kernel"], rec["stage"])]
            e["pol"].add(d["policy"]); e["maxsi"] = max(e["maxsi"], d.get("sub_index") or 0)
        elif d.get("round_type") == "random":
            bykey[(rec["kernel"], rec["stage"])]["rand"].append(d.get("round_index") or 0)
    for (k, stage), e in sorted(bykey.items()):
        ck = out.get(k, 0.5)
        if e["pol"]:
            rounds = proto[stage] + n_a * len(e["pol"]) * (e["maxsi"] + 1)
            est = STARTUP + rounds * ck
            ctot += est
            detail.append(("ctrl %s/%s" % (k, stage), rounds, est))
        for ri in sorted(set(e["rand"])):
            rounds = max(n_a, ri + 1)
            est = STARTUP + rounds * ck
            ctot += est
            detail.append(("ctrl %s/%s rand%d" % (k, stage, ri), rounds, est))
    btot = 0
    for rec in inv:
        d = rec.get("divergence") or {}
        if d.get("round_type") is None:
            continue
        ck = out.get(rec["kernel"], 0.5)
        if d.get("round_type") == "stress":
            rounds = proto[rec["stage"]] + n_b * ((d.get("sub_index") or 0) + 1)
        else:
            rounds = (d.get("round_index") or 0) + 1
        btot += STARTUP + rounds * ck
    return ctot, btot, detail

for n_a in (10, 15, 20, 30, 50):
    ct, bt, _ = cost(n_a, 20)
    print("n_A=%-3d control %5.2f h   confirm(worst) %5.2f h   total %5.2f h"
          % (n_a, ct/3600, bt/3600, (ct+bt)/3600))
ct, bt, detail = cost(20, 20)
print("\nn_A=20 control cell detail:")
for name, rounds, est in sorted(detail, key=lambda x: -x[2]):
    print("  %-34s rounds=%-4d est=%6.0f s" % (name, rounds, est))
'''
open("_wc27_tmp.py","w").write(script)
s = c.open_sftp(); s.put("_wc27_tmp.py", "/root/mk_v2/_wc27_tmp.py"); s.close()
R(c, "/root/miniconda3/bin/python /root/mk_v2/_wc27_tmp.py", timeout=300)
R(c, "tail -2 /root/mk_v2_runs/e1/witness_confirmation/audit.log; date")
c.close()
