"""Who placed the 21:45 brake, and is the critical path back?"""
import io

import _remote

SCRIPT = r'''
import json, sys, time
from pathlib import Path
sys.path.insert(0, "/root/mk_v2")
import _b9_brake as B

OUT = Path("/root/mk_v2_runs/e3_b9_calib")
E1 = Path("/root/mk_v2_runs/e1")
print("=== %s ===" % time.strftime("%Y-%m-%dT%H:%M:%S%z"))

print("[critical path right now]")
procs = B.critical_path_processes()
for needle, pid, cl in procs:
    print("   %-24s pid=%-7d %s" % (needle, pid, cl[:110]))
if not procs:
    print("   none")
print("[gpu compute apps]", B.gpu_compute_apps() or "none")

print("\n[chain trigger log tail]")
for line in (OUT / "chain_trigger.log").read_text(
        encoding="utf-8").splitlines()[-18:]:
    print("  ", line[:200])

print("\n[adopted legacy marker]")
p = B.brake_dir() / (B.PREFIX + B.LEGACY_OWNER)
if p.is_file():
    d = json.loads(p.read_text())
    print("   placed_at:", d.get("placed_at"))
    print("   original_text:")
    for line in (d.get("original_text") or "").splitlines():
        print("     ", line[:160])

print("\n[audit activity since 21:40]")
wc = E1 / "witness_confirmation"
if wc.is_dir():
    for q in sorted(wc.rglob("*")):
        try:
            st = q.stat()
        except OSError:
            continue
        if st.st_mtime > time.time() - 1500:
            print("   %-64s %s" % (str(q.relative_to(wc)),
                  time.strftime("%H:%M:%S", time.localtime(st.st_mtime))))

print("\n[lanes / queue]")
print("  lanes:", B.find_processes("calib_driver_v2.py") or "none")
st = json.loads((OUT / "queue_state.json").read_text())
print("  pending=%d claimed=%s done=%d" % (len(st["pending"]),
                                           list(st["claimed"]), len(st["done"])))
for name in ("lane_v2_0.log", "lane_v2_1.log"):
    q = OUT / name
    if q.is_file():
        print("  [%s]" % name)
        for line in q.read_text().splitlines()[-3:]:
            print("     ", line[:170])
rows = []
for q in sorted(OUT.glob("calibration_v2_lane*.jsonl")):
    for line in q.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
print("  v2 rows: %d" % len(rows))
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT.encode()), "/root/_brake_who.py")
sftp.close()
_remote.run(c, "/root/miniconda3/bin/python /root/_brake_who.py", timeout=300)
c.close()
