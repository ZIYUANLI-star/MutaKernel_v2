
import json, glob
for p in sorted(glob.glob("/root/mk_v2_runs/e1/witness_confirmation/cells/ctrl__L1_P37*.json")):
    r = json.load(open(p))
    print("=" * 70)
    print(r["cell_id"], "state:", r["validation_status"], "wall", r["wall_s"],
          "planned_rounds", r["planned_rounds"], "executed", len(r["rounds"]))
    print("cfg:", json.dumps(r["cfg_digest"]))
    for t in r["rounds"]:
        print("   si=%s seed=%s %-12s max_abs_error=%s %s"
              % (t["sub_index"], t["seed"], t["status"], t["max_abs_error"],
                 t["reason"][:80]))
    d = r.get("divergence") or {}
    if d:
        print("DIVERGENCE:", json.dumps({k: d.get(k) for k in
              ("round_type", "policy", "sub_index", "seed", "detail")}))
        for m in ((d.get("oracle") or {}).get("mismatches") or []):
            print("   mismatch:", m.get("message"))
