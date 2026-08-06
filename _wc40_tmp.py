
import json, glob, collections
D = "/root/mk_v2_runs/e1/witness_confirmation/cells/"
for p in sorted(glob.glob(D + "ctrl__*.json")):
    r = json.load(open(p))
    st = collections.Counter(t["status"] for t in r["rounds"])
    if r["validation_status"] != "pass" or r.get("round_timeouts"):
        print("%-46s status=%-12s rounds=%-3d %s timeouts=%s wall=%.0f"
              % (r["cell_id"], r["validation_status"], len(r["rounds"]),
                 dict(st), r.get("round_timeouts"), r["wall_s"]))
        for t in r["rounds"]:
            if t["status"] != "pass":
                print("      si=%s seed=%s %s | %s" % (t["sub_index"], t["seed"],
                                                       t["status"], t["reason"][:120]))
print("---- summary of all control cells ----")
agg = collections.Counter()
for p in sorted(glob.glob(D + "ctrl__*.json")):
    r = json.load(open(p))
    st = collections.Counter(t["status"] for t in r["rounds"])
    agg[(r["validation_status"], "fail>0" if st["fail"] else "no_fail")] += 1
print(dict(agg))
