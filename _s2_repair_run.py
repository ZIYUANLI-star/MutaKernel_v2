"""Deploy + run the stage-2 queue schema repair, then watch first launch."""
import time
import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_s2_repair_src.py", "/root/mk_v2/_s2_repair.py")
sftp.close()
_, o, e = _remote.run(
    c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _s2_repair.py",
    timeout=120, echo=False)
print(o)
if e.strip():
    print("STDERR:\n" + e[-2000:])
if "S2_REPAIR_DONE" not in o:
    raise SystemExit("repair failed")

print("waiting 90s for guard cycle + driver launch...")
time.sleep(90)
_, o, _ = _remote.run(c, (
    "pgrep -af '[_]b9_calib_driver_v2' | head -4; echo ---; "
    "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; echo ---; "
    "tail -6 /root/mk_v2_runs/e3_b9_calib/lane_v2_0.log; echo ---; "
    "tail -4 /root/mk_v2_runs/e3_b9_calib/lane_v2_1.log"),
    timeout=60, echo=False)
print(o)
c.close()
