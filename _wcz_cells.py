"""Inspect the anomalous control cells in detail (read-only)."""
import json
import pathlib

import _wcx

PY = "/root/miniconda3/bin/python"
WC = "/root/mk_v2_runs/e1/witness_confirmation"
LOCAL = pathlib.Path("_wc_remote")
LOCAL.mkdir(exist_ok=True)

INSPECT = """
import json, glob, os, collections
d = "%s/cells"
files = sorted(glob.glob(d + "/*.json"))
print("CELL_FILES", len(files))
plan = json.load(open("%s/plan.json"))
planned = {c["cell_id"] for c in plan["control_cells"]} | {c["cell_id"] for c in plan["confirm_cells"]}
have = {os.path.basename(f)[:-5] for f in files}
print("PLANNED", len(planned), "HAVE", len(have))
print("STALE_NOT_IN_PLAN", sorted(have - planned))
print("MISSING_CTRL", len([c for c in plan["control_cells"] if c["cell_id"] not in have]))
print("MISSING_CONF", len([c for c in plan["confirm_cells"] if c["cell_id"] not in have]))
print("=== control cells: status summary ===")
for c in plan["control_cells"]:
    p = os.path.join(d, c["cell_id"] + ".json")
    if not os.path.exists(p):
        continue
    r = json.load(open(p))
    st = collections.Counter(x["status"] for x in r["rounds"])
    if r.get("validation_status") == "pass" and not st.get("fail"):
        continue
    print(" ", c["cell_id"], "vs=", r.get("validation_status"), "timed_out=",
          r.get("timed_out"), "valid_rounds=", r.get("valid_rounds"),
          "round_timeouts=", r.get("round_timeouts"), "wall=", r.get("wall_s"),
          "budget=", r.get("worker_budget_s"), "statuses=", dict(st))
    if r.get("divergence"):
        print("      divergence:", json.dumps(r["divergence"])[:400])
    if r.get("errors"):
        print("      errors:", json.dumps(r["errors"])[:300])
""" % (WC, WC)

DUMP = ["ctrl__L1_P37__equiv__boundary_last_element",
        "ctrl__L1_P39__equiv__sparse",
        "ctrl__L1_P17__equiv__head_heavy"]


def main():
    with _wcx.Session(label="cells ") as s:
        s.run("cat > /tmp/_wcz_inspect.py << 'PYEOF'\n%s\nPYEOF" % INSPECT, timeout=90)
        print(s.out("%s /tmp/_wcz_inspect.py 2>&1" % PY, timeout=240,
                    default="FAILED:").rstrip(), flush=True)
        for cid in DUMP:
            txt = s.out("cat %s/cells/%s.json 2>/dev/null" % (WC, cid),
                        timeout=120, default="FAILED:")
            (LOCAL / ("%s.json" % cid)).write_text(txt, encoding="utf-8")
            print("\n##### %s (%d bytes) #####" % (cid, len(txt)), flush=True)
            try:
                r = json.loads(txt)
            except Exception:
                print(txt[:1500])
                continue
            print("validation_status=%s timed_out=%s valid_rounds=%s wall=%s budget=%s"
                  % (r.get("validation_status"), r.get("timed_out"),
                     r.get("valid_rounds"), r.get("wall_s"), r.get("worker_budget_s")))
            print("cfg_digest=%s" % json.dumps(r.get("cfg_digest")))
            print("positions=%s witness_sub=%s probe_ids=%s"
                  % (r.get("positions"), r.get("witness_sub_indices"),
                     r.get("probe_ids")))
            for i, x in enumerate(r.get("rounds") or [], 1):
                print("  r%-3d %s/%s si=%s seed=%s %s err=%s %s"
                      % (i, x.get("round_type"), x.get("policy"), x.get("sub_index"),
                         x.get("seed"), x.get("status"), x.get("max_abs_error"),
                         (x.get("reason") or "")[:110]))
            if r.get("divergence"):
                print("divergence:", json.dumps(r["divergence"])[:900])
    print("\nCELLS_DONE")


if __name__ == "__main__":
    main()
