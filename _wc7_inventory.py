import _remote
c = _remote.connect()
R = _remote.run
script = r'''
import json, glob, os, collections

E1 = "/root/mk_v2_runs/e1"
ARCHIVE_HINTS = (".bak", "_env_v1", "_inc_archive", "_timeout_v1", "_signoff_archive")

cse_files = [p for p in sorted(glob.glob(E1 + "/cse_observations*.jsonl"))
             if not any(h in os.path.basename(p) for h in ARCHIVE_HINTS)]
print("CSE source files:")
for p in cse_files:
    print("  ", os.path.basename(p))

best = {}
for p in cse_files:
    for line in open(p):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        pid = r["probe_id"]
        ts = r.get("finished_at") or ""
        prev = best.get(pid)
        if prev is None or ts >= prev[0]:
            best[pid] = (ts, r, os.path.basename(p))
print("CSE resolved probes:", len(best))
cnt = collections.Counter(v[1].get("outcome") for v in best.values())
print("CSE outcomes:", dict(cnt))

def witness_rounds(r):
    out = []
    for t in (r.get("trials") or []):
        if t.get("status") == "fail":
            mae = None
            orc = t.get("oracle") or {}
            for m in (orc.get("mismatches") or []):
                v = m.get("max_abs_error")
                if v is not None:
                    mae = v if mae is None else max(mae, v)
            out.append({"round_type": t.get("round_type"),
                        "round_index": t.get("round_index"),
                        "seed": t.get("seed"),
                        "policy": t.get("policy"),
                        "sub_index": t.get("sub_index"),
                        "max_abs_error": mae,
                        "reason": (t.get("reason") or "")[:160]})
    return out

fals = {pid: v for pid, v in best.items() if "FALSIF" in str(v[1].get("outcome"))}
print("\n=== CSE FALSIFIED:", len(fals), "===")
inv = []
for pid, (ts, r, src) in sorted(fals.items()):
    wr = witness_rounds(r)
    rec = {"stage": "cse", "probe_id": pid, "kernel": r.get("kernel"),
           "operator": r.get("operator_name"), "fault_class": r.get("fault_class"),
           "src": src, "valid_rounds": r.get("valid_rounds"),
           "divergence": r.get("divergence"), "witness_rounds": wr}
    inv.append(rec)
    print(json.dumps(rec, ensure_ascii=False)[:1400])
    print("--")

eq = [json.loads(l) for l in open(E1 + "/equiv_observations.jsonl") if l.strip()]
print("\nEQUIV rows:", len(eq),
      dict(collections.Counter(r.get("evidence_grade") for r in eq)))
wit = [r for r in eq if "WITNESS" in str(r.get("evidence_grade"))]
print("=== EQUIV WITNESSED:", len(wit), "===")
for r in sorted(wit, key=lambda x: x["probe_id"]):
    wr = witness_rounds(r)
    rec = {"stage": "equiv", "probe_id": r["probe_id"], "kernel": r.get("kernel"),
           "operator": r.get("operator_name"), "fault_class": r.get("fault_class"),
           "src": "equiv_observations.jsonl", "valid_rounds": r.get("valid_rounds"),
           "divergence": r.get("divergence"), "witness_rounds": wr}
    inv.append(rec)

json.dump(inv, open("/root/mk_v2_runs/e1/_wc_witness_inventory.json", "w"),
          indent=1, ensure_ascii=False)

kern = collections.Counter(r["kernel"] for r in inv)
print("\n=== kernels carrying witnesses:", len(kern), "===")
for k, n in sorted(kern.items(), key=lambda kv: (-kv[1], kv[0])):
    stages = collections.Counter(r["stage"] for r in inv if r["kernel"] == k)
    print(f"  {k:10s} n={n:3d}  cse={stages.get('cse',0)} equiv={stages.get('equiv',0)}")

kern_cse = collections.Counter(r["kernel"] for r in inv if r["stage"] == "cse")
kern_eq = collections.Counter(r["kernel"] for r in inv if r["stage"] == "equiv")
print("distinct kernels total:", len(kern),
      "cse-only-kernels:", len(kern_cse), "equiv-kernels:", len(kern_eq))
print("INVENTORY_DONE")
'''
open("_wc7_tmp.py", "w").write(script)
s = c.open_sftp(); s.put("_wc7_tmp.py", "/root/mk_v2/_wc7_tmp.py"); s.close()
R(c, "/root/miniconda3/bin/python /root/mk_v2/_wc7_tmp.py", timeout=600)
c.close()
print("DONE")
