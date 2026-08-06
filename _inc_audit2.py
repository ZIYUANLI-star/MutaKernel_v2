"""Round 2 driver: run pass-2 inventory remotely, fetch and pretty-print."""
import json

import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_inc_inventory2_remote.py", "/root/mk_v2/_inc_inventory2_remote.py")
_remote.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python "
               "_inc_inventory2_remote.py", timeout=180)
sftp.get("/root/mk_v2_runs/e1/_inc_inventory2_report.json",
         "_inc_inventory2_report.json")
sftp.close()
c.close()

rep = json.load(open("_inc_inventory2_report.json", encoding="utf-8"))
print("== guard v9 script ==")
print(rep["guard_v9"] or "(missing)")
print("== lane logs ==")
for s in rep["lane_logs"]:
    print(f"-- lane{s['lane']} guard lines:")
    for l in s["guard_lines"]:
        print("  ", l[:160])
    print(f"-- lane{s['lane']} tail:")
    for l in s["tail"]:
        print("  ", l[:160])
print("\n== fresh 3/4/5 records ==")
for f in rep["fresh_345"]:
    print(" ", f)
print("\n== equiv closure ==")
print(json.dumps(rep["equiv_closure"], indent=1))
print("\n== equiv merged INC record ==")
print(json.dumps(rep.get("equiv_merged_inc"), indent=1)[:1800])
print("\n== vram classes ==", rep["vram_classes"])
print("== per-kernel equiv medians ==", rep["per_kernel_medians"])
for i, ks in rep["lane_kernels"].items():
    print(f"lane{i} kernels ({len(ks)}):", ks)
print("AUDIT2_DONE")
