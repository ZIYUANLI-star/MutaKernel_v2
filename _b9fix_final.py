# -*- coding: utf-8 -*-
"""Final consolidated verification: redeploy the prep with the first-wave ETA,
re-run the whole test suite plus the neighbouring suites, and confirm the run
directory is still paused with nothing running."""
import hashlib

import _remote as R

PY = "/root/miniconda3/bin/python"

c = R.connect()
sftp = c.open_sftp()
for local, remote in [("_b9_resume_prep.py", "/root/mk_v2/_b9_resume_prep.py")]:
    with open(local, "rb") as fh:
        body = fh.read().replace(b"\r\n", b"\n")
    with sftp.open(remote, "wb") as fh:
        fh.write(body)
    print("uploaded", remote, hashlib.md5(body).hexdigest())
sftp.close()

print()
print("### ETA incl. first wave")
R.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= %s _b9_resume_prep.py 2>&1 | tail -22" % PY,
      timeout=600)

print()
print("### full test suite (new + every suite that imports the B9 port)")
R.run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=24 MKL_NUM_THREADS=24 "
         "%s -m pytest tests/test_b9_error_stats_bitexact.py tests/test_e3_ports.py "
         "tests/test_validation_core.py -q 2>&1 | tail -8" % PY, timeout=3600)

print()
print("### deployed file inventory")
R.run(c, "cd /root/mk_v2 && md5sum src/experiments/external_ports/b9_seeded_fuzzing.py "
         "src/experiments/external_ports/b9_seeded_fuzzing.py.bak_quantile_fix "
         "tests/test_b9_error_stats_bitexact.py _b9_precheck.py _b9_resume_prep.py "
         "_b9_calib_driver_v2.py; "
         "ls -l /root/mk_v2_runs/e3_b9_calib/ | tail -20", timeout=120)

print()
print("### still paused, nothing running, GPU untouched by us")
R.run(c, "ls /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN "
         "/root/mk_v2_runs/e3_b9_calib/queue_state.json 2>&1; "
         "%s -c \"import os,sys;from pathlib import Path;\n"
         "def pp(p):\n"
         " [sys.exit(0) for _ in []]\n\" 2>/dev/null; "
         "echo '--- b9 processes (proc scan, self excluded) ---'; "
         "%s /root/mk_v2/_b9_precheck.py 2>&1 | grep -E 'driver|guard|GPU|worker'" % (PY, PY),
      timeout=300)
c.close()
print("FINAL_DONE")
