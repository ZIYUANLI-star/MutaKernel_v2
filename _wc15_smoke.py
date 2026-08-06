import _remote
c = _remote.connect()
R = _remote.run
s = c.open_sftp(); s.put("_wc_audit.py", "/root/mk_v2/_wc_audit.py"); s.close()
print("=== plan (deduped) ===")
R(c, "cd /root/mk_v2 && /root/miniconda3/bin/python _wc_audit.py plan --n-a 50 --n-b 20 2>&1 | head -12", timeout=600)
print("=== b9 fully stopped? (proc scan, no pgrep -f) ===")
script = r'''
import os
from pathlib import Path
def ppid(p):
    try:
        for line in open("/proc/%d/status" % p):
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except OSError:
        pass
    return 0
excl, p = set(), os.getpid()
while p and p != 1:
    excl.add(p); p = ppid(p)
needles = ["_b9_calib_driver", "guard_b9", "_mutant_worker", "_b9_chain_trigger",
           "_b9_stage1_chain", "keepalive_chain"]
for e in sorted(os.listdir("/proc")):
    if not e.isdigit() or int(e) in excl:
        continue
    try:
        raw = Path("/proc/%s/cmdline" % e).read_bytes()
    except OSError:
        continue
    cl = raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()
    for n in needles:
        if n in cl:
            print(e, "->", cl[:150])
            break
print("--- markers ---")
import glob
for f in sorted(glob.glob("/root/mk_v2_runs/e3_b9_calib/*")):
    if os.path.basename(f).isupper() or "PAUSED" in f:
        print(" ", f)
'''
open("_wc15_tmp.py","w").write(script)
s = c.open_sftp(); s.put("_wc15_tmp.py", "/root/mk_v2/_wc15_tmp.py"); s.close()
R(c, "/root/miniconda3/bin/python /root/mk_v2/_wc15_tmp.py", timeout=180)
print("=== b9 checkpoint integrity ===")
R(c, "wc -l /root/mk_v2_runs/e3_b9_calib/calibration_v2_lane*.jsonl; cat /root/mk_v2_runs/e3_b9_calib/completed_v2_lane*.json; echo; nvidia-smi --query-gpu=memory.used --format=csv,noheader; free -g | sed -n 2p; grep -i oom /sys/fs/cgroup/memory.events")
c.close()
