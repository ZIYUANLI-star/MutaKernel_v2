import _remote
c = _remote.connect()
R = _remote.run
script = r'''
import json, collections
E1 = "/root/mk_v2_runs/e1"
inv = json.load(open(E1 + "/_wc_witness_inventory.json"))
kernels = sorted({r["kernel"] for r in inv})
eq = [json.loads(l) for l in open(E1 + "/equiv_observations.jsonl") if l.strip()]
per = collections.defaultdict(list)
for r in eq:
    k = r.get("kernel")
    tr = r.get("trials") or []
    w = r.get("wall_ms")
    if k in kernels and tr and w:
        per[k].append(w / len(tr) / 1000.0)
print("kernel  true_wall_s_per_round (median over probes)  n_probes")
out = {}
for k in kernels:
    v = sorted(per[k])
    if v:
        m = v[len(v)//2]
        out[k] = m
        print("  %-8s %8.2f s   (min %.2f max %.2f, n=%d)" % (k, m, v[0], v[-1], len(v)))
json.dump(out, open(E1 + "/_wc_round_wall.json", "w"), indent=1)

# projected cell wall for the current plan
plan = json.load(open(E1 + "/witness_confirmation/plan.json"))
tot = 0
print("\nprojected control cell wall (startup 70s + rounds x true cost):")
for cell in plan["control_cells"]:
    m = out.get(cell["kernel"], 0.5)
    est = 70 + cell["rounds"] * m
    tot += est
    print("  %-42s rounds=%-5d est=%7.0f s" % (cell["cell_id"], cell["rounds"], est))
print("control total est %.1f h" % (tot / 3600))
tot2 = 0
for cell in plan["confirm_cells"]:
    m = out.get(cell["kernel"], 0.5)
    tot2 += 70 + cell["rounds"] * m
print("confirm total est (worst case, no early abort) %.1f h" % (tot2 / 3600))
'''
open("_wc26_tmp.py","w").write(script)
s = c.open_sftp(); s.put("_wc26_tmp.py", "/root/mk_v2/_wc26_tmp.py"); s.close()
R(c, "/root/miniconda3/bin/python /root/mk_v2/_wc26_tmp.py", timeout=300)
R(c, "tail -3 /root/mk_v2_runs/e1/witness_confirmation/audit.log; date")
c.close()
