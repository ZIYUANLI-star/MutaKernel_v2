# -*- coding: utf-8 -*-
"""Deploy the resume machinery (write only) and exercise its read-only paths.

Nothing here starts a lane: only the precheck and the prep dry-run are run,
both of which are read-only.  The GPU is never touched.
"""
import hashlib

import _remote as R

FILES = [
    ("_b9_precheck.py", "/root/mk_v2/_b9_precheck.py", False),
    ("_b9_resume_prep.py", "/root/mk_v2/_b9_resume_prep.py", False),
    ("_b9_calib_driver_v2.py", "/root/mk_v2/_b9_calib_driver_v2.py", False),
    ("_b9_guard_v2.sh", "/root/mk_v2_runs/e3_b9_calib/guard_b9_v2.sh", True),
    ("_b9_resume.sh", "/root/mk_v2_runs/e3_b9_calib/resume_b9.sh", True),
    ("_b9_pause_v2.sh", "/root/mk_v2_runs/e3_b9_calib/pause_b9.sh", True),
]
PY = "/root/miniconda3/bin/python"

c = R.connect()
sftp = c.open_sftp()
for local, remote, _ in FILES:
    with open(local, "rb") as fh:
        body = fh.read().replace(b"\r\n", b"\n")
    with sftp.open(remote, "wb") as fh:
        fh.write(body)
    print("uploaded %-24s -> %s  md5=%s"
          % (local, remote, hashlib.md5(body).hexdigest()))
sftp.close()

R.run(c, "chmod +x " + " ".join(r for _, r, x in FILES if x), timeout=60)
R.run(c, "ls -l /root/mk_v2/_b9_precheck.py /root/mk_v2/_b9_resume_prep.py "
         "/root/mk_v2/_b9_calib_driver_v2.py /root/mk_v2_runs/e3_b9_calib/*.sh", timeout=60)

print()
print("### syntax check (compile only, nothing executed)")
R.run(c, "cd /root/mk_v2 && %s -m py_compile _b9_precheck.py _b9_resume_prep.py "
         "_b9_calib_driver_v2.py && echo PY_COMPILE_OK; "
         "for s in /root/mk_v2_runs/e3_b9_calib/resume_b9.sh "
         "/root/mk_v2_runs/e3_b9_calib/guard_b9_v2.sh "
         "/root/mk_v2_runs/e3_b9_calib/pause_b9.sh; do bash -n $s && echo \"BASH_OK $s\"; done"
      % PY, timeout=180)

print()
print("### precheck (read-only; expected to FAIL while the critical path runs)")
R.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= %s _b9_precheck.py 2>&1" % PY,
      timeout=300)

print()
print("### prep dry-run (read-only): plan + memory budget + ETA")
R.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= %s _b9_resume_prep.py 2>&1" % PY,
      timeout=600)

print()
print("### resume_b9.sh --dry-run (read-only wrapper check)")
R.run(c, "bash /root/mk_v2_runs/e3_b9_calib/resume_b9.sh --dry-run 2>&1 | tail -32",
      timeout=600)

print()
print("### confirm nothing was started and the pause marker is still in place")
R.run(c, "ls -l /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN; "
         "ls /root/mk_v2_runs/e3_b9_calib/queue_state.json 2>&1; "
         "pgrep -af '_b9_calib_driver' | head; "
         "pgrep -af 'guard_b9' | head; "
         "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; "
         "echo '--- critical path ---'; "
         "ps -eo pid,rss,etimes,args | grep '_mutant_[w]orker' | awk '{print $1,$2,$3}'",
      timeout=120)
c.close()
print("DEPLOY_RESUME_DONE")
