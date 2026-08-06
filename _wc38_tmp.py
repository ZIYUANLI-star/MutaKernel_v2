
"""Per-witness passing-round breakdown, needed for the WC-1 re-grading rule."""
import json, glob, os, collections
E1 = "/root/mk_v2_runs/e1"
ARCH = (".bak", "_env_v1", "_inc_archive", "_timeout_v1", "_signoff_archive")
inv = json.load(open(E1 + "/_wc_witness_inventory.json"))
want = {r["probe_id"]: r["stage"] for r in inv}

out = {}
def take(rec, stage):
    pid = rec["probe_id"]
    if want.get(pid) != stage:
        return
    tr = rec.get("trials") or []
    rp = sum(1 for t in tr if t.get("round_type") == "random" and t.get("status") == "pass")
    sp = sum(1 for t in tr if t.get("round_type") == "stress" and t.get("status") == "pass")
    inc = sum(1 for t in tr if t.get("status") == "inconclusive")
    fail = sum(1 for t in tr if t.get("status") == "fail")
    ts = rec.get("finished_at") or ""
    prev = out.get(pid)
    if prev is None or ts >= prev.get("finished_at", ""):
        out[pid] = {"stage": stage, "random_pass": rp, "stress_pass": sp,
                    "inconclusive": inc, "fail": fail, "total_trials": len(tr),
                    "valid_rounds": rec.get("valid_rounds"),
                    "finished_at": ts}

for p in [q for q in sorted(glob.glob(E1 + "/cse_observations*.jsonl"))
          if not any(h in os.path.basename(q) for h in ARCH)]:
    for line in open(p):
        line = line.strip()
        if line:
            take(json.loads(line), "cse")
for line in open(E1 + "/equiv_observations.jsonl"):
    line = line.strip()
    if line:
        take(json.loads(line), "equiv")

json.dump(out, open(E1 + "/_wc_round_counts.json", "w"), indent=1)
print("witnesses with counts:", len(out), "of", len(want))
print("\n=== CSE FALSIFIED: evidence left if the witness round is voided ===")
print("thresholds: valid>=77, random_pass>=30, stress_pass>=42")
for pid, v in sorted(out.items()):
    if v["stage"] != "cse":
        continue
    ok = (v["valid_rounds"] or 0) >= 77 and v["random_pass"] >= 30 and v["stress_pass"] >= 42
    print("  %-32s valid=%-4s rand_pass=%-3d stress_pass=%-3d -> %s"
          % (pid, v["valid_rounds"], v["random_pass"], v["stress_pass"],
             "STILL_LIKELY_EQUIVALENT (thresholds met)" if ok else "DEFICIT -> requeue"))
print("\n=== equiv WITNESSED: stress_pass (threshold >=8) ===")
d = collections.Counter()
for pid, v in sorted(out.items()):
    if v["stage"] != "equiv":
        continue
    d["ok" if v["stress_pass"] >= 8 else "deficit"] += 1
print("  ", dict(d))
for pid, v in sorted(out.items()):
    if v["stage"] == "equiv" and v["stress_pass"] < 8:
        print("   deficit: %-32s rand_pass=%-3d stress_pass=%-3d" % (pid, v["random_pass"], v["stress_pass"]))
