"""Handover state check: critical path, B9 pause state, deployed scripts."""
import io

import _remote

SCAN = r'''
import os
pats = ["_mutant_worker.py", "run_e1_cse_falsify.py", "_signoff_orch.py",
        "b9", "B9", "resume_b9", "run_e3_external", "chain"]
me = os.getpid()
rows = []
for p in os.listdir("/proc"):
    if not p.isdigit():
        continue
    try:
        with open("/proc/%s/cmdline" % p, "rb") as f:
            cl = f.read().replace(b"\x00", b" ").decode(errors="replace").strip()
    except Exception:
        continue
    if not cl:
        continue
    if any(x in cl for x in pats):
        try:
            with open("/proc/%s/stat" % p) as f:
                st = f.read()
            ppid = st.split(")")[-1].split()[1]
        except Exception:
            ppid = "?"
        rows.append((int(p), ppid, cl[:220]))
for pid, ppid, cl in sorted(rows):
    print(pid, "ppid=" + str(ppid), cl)
print("SCAN_DONE me=%d" % me)
'''

c = _remote.connect()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCAN.encode()), "/root/_h1_scan.py")
sftp.close()

cmds = [
    "date -Iseconds; uptime",
    "ls -la /root/mk_v2_runs/e1/ | head -60",
    "ls -la /root/mk_v2_runs/e1/SIGNOFF_ORCH_DONE 2>&1",
    "ls -la /root/mk_v2_runs/e3_b9_calib/ | head -100",
    "cat /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN 2>&1",
    "nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv",
    "nvidia-smi --query-gpu=memory.total,memory.used,utilization.gpu --format=csv",
    "grep -i oom /proc/vmstat",
    "free -g | sed -n '1,3p'; nproc",
    "ls -la /root/mk_v2_runs/e3_b9_calib/*.sh /root/mk_v2_runs/e1/*.sh 2>&1",
    "/root/miniconda3/bin/python /root/_h1_scan.py",
]
for cmd in cmds:
    print("\n### " + cmd)
    _remote.run(c, cmd, timeout=180)
c.close()
print("\nH1_DONE")
