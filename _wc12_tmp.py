
import json, glob, os
OUT = "/root/mk_v2_runs/e3_b9_calib"
rows = []
for p in sorted(glob.glob(OUT + "/calibration_lane*.jsonl")) + \
        sorted(glob.glob(OUT + "/calibration_v2_lane*.jsonl")):
    for line in open(p):
        line = line.strip()
        if line:
            r = json.loads(line)
            rows.append((os.path.basename(p), r.get("unit") or r.get("unit_id"),
                         r.get("status"), r.get("wall_s") or r.get("wall"),
                         r.get("peak_rss_gb")))
for r in rows:
    print(r)
ust = json.load(open(OUT + "/unit_size_table.json"))
key = "L1_P7__float32"
if isinstance(ust, dict):
    v = ust.get(key)
    print("\nunit_size_table[L1_P7__float32] =", json.dumps(v)[:600] if v else "absent")
    print("keys sample:", list(ust)[:5])
qs = json.load(open(OUT + "/queue_state.json"))
print("\nclaimed:", json.dumps(qs.get("claimed"), indent=1))
print("pending:", qs.get("pending"))
print("done count:", len(qs.get("done", {})))
