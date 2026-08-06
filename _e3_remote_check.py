# -*- coding: utf-8 -*-
"""Remote recon for E2/E3: corpora presence, python deps, e1 status (read-only)."""
import _remote as R

c = R.connect()
cmds = [
    "ls /root/mk_v2/external 2>/dev/null",
    "ls /root/mk_v2/external/C3_ai_cuda_engineer 2>/dev/null | head",
    "ls /root/mk_v2/external/C4_tritonbench/data 2>/dev/null | head",
    "ls /root/mk_v2/external/C2_cuda_l1/optimized_cuda_code 2>/dev/null | head",
    "ls /root/mk_v2/external/C5_kernelbench_samples 2>/dev/null | head",
    "ls /root/mk_v2/external/B7_robust_kbench 2>/dev/null | head",
    "ls /root/mk_v2/external/B8_kernelbenchx/data 2>/dev/null | head",
    "ls /root/mk_v2/KernelBench/KernelBench 2>/dev/null | head",
    "/root/miniconda3/bin/python -c \"import pyarrow, pytest, torch; print('pyarrow', pyarrow.__version__, 'pytest', pytest.__version__, 'torch', torch.__version__)\"",
    "which compute-sanitizer; compute-sanitizer --version 2>/dev/null | head -2",
    "ps aux | grep run_e1 | grep -v grep | head -3",
    "ls /root/mk_v2_runs 2>/dev/null",
    "ls /root/mk_v2/scripts/reconcile_corpora.py /root/mk_v2/scripts/run_e3_external.py /root/mk_v2/scripts/b11_compute_sanitizer.py /root/mk_v2/scripts/extract_contracts.py 2>&1",
    "cd /root/mk_v2 && git log --oneline -2 2>/dev/null; git status --porcelain 2>/dev/null | head -20",
]
for cmd in cmds:
    print("### " + cmd)
    R.run(c, cmd, timeout=180)
c.close()
print("REMOTE_CHECK_DONE")
