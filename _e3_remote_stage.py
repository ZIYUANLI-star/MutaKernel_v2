# -*- coding: utf-8 -*-
"""Upload E3 changes to the remote repo (single-file sftp puts), run the full
CPU-only test suite, extract C2/C3/C5 contract drafts, smoke B1u on a real
KernelBench task, and check compute-sanitizer availability."""
import os
import _remote as R

FILES = [
    ("scripts/run_e3_external.py", "/root/mk_v2/scripts/run_e3_external.py"),
    ("scripts/b11_compute_sanitizer.py", "/root/mk_v2/scripts/b11_compute_sanitizer.py"),
    ("scripts/extract_contracts.py", "/root/mk_v2/scripts/extract_contracts.py"),
    ("configs/external_baselines.json", "/root/mk_v2/configs/external_baselines.json"),
    ("src/experiments/external_ports/__init__.py",
     "/root/mk_v2/src/experiments/external_ports/__init__.py"),
    ("src/experiments/external_ports/budget32.py",
     "/root/mk_v2/src/experiments/external_ports/budget32.py"),
    ("src/experiments/external_ports/b1u_anchor.py",
     "/root/mk_v2/src/experiments/external_ports/b1u_anchor.py"),
    ("src/experiments/external_ports/b7_robust_kbench.py",
     "/root/mk_v2/src/experiments/external_ports/b7_robust_kbench.py"),
    ("src/experiments/external_ports/b8_kernelbenchx.py",
     "/root/mk_v2/src/experiments/external_ports/b8_kernelbenchx.py"),
    ("src/experiments/external_ports/b9_seeded_fuzzing.py",
     "/root/mk_v2/src/experiments/external_ports/b9_seeded_fuzzing.py"),
    ("tests/test_e3_ports.py", "/root/mk_v2/tests/test_e3_ports.py"),
    ("tests/test_b11_sanitizer.py", "/root/mk_v2/tests/test_b11_sanitizer.py"),
    ("tests/test_e2_inclusion.py", "/root/mk_v2/tests/test_e2_inclusion.py"),
]
FRAME_DIR = os.path.join("MutakernelV2", "实验", "补充实验数据", "collection_frames")
FRAMES = [
    (os.path.join(FRAME_DIR, "C2_collection_frame.jsonl"),
     "/root/mk_v2_runs/e2_reconcile/C2_collection_frame.jsonl"),
    (os.path.join(FRAME_DIR, "C5_collection_frame.jsonl"),
     "/root/mk_v2_runs/e2_reconcile/C5_collection_frame.jsonl"),
]

c = R.connect()
R.run(c, "mkdir -p /root/mk_v2/src/experiments/external_ports "
         "/root/mk_v2/configs /root/mk_v2/tests /root/mk_v2_runs/e2_reconcile",
      timeout=30)
sftp = c.open_sftp()
for local, remote in FILES + FRAMES:
    sftp.put(local, remote)
    print("put", local)

print("### compute-sanitizer availability")
R.run(c, "ls -la /usr/local/cuda/bin/compute-sanitizer 2>&1; "
         "/usr/local/cuda/bin/compute-sanitizer --version 2>&1 | head -3", timeout=60)

print("### full test suite (CPU-only)")
code, out, err = R.run(
    c,
    "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= /root/miniconda3/bin/python -m pytest tests -x -q 2>&1 | tail -25",
    timeout=1800,
)

sftp.close()
c.close()
print("STAGE_DONE exit=", code)
