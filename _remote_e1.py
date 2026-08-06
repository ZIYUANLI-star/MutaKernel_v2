"""E1-E4 readiness helper for the remote A800 (never touches the GPU while run5 is live).

Steps:
  probe   - read-only recon: run5 status, dirs, deps
  patch   - upload _e1_patch.tar.gz and extract into /root/mk_v2
  test    - run the CPU-only test suite + smoke of new drivers (CUDA_VISIBLE_DEVICES='')
"""
import sys

from _remote import connect, run

PY = "/root/miniconda3/bin/python"
step = sys.argv[1] if len(sys.argv) > 1 else "probe"
c = connect()

if step == "probe":
    for cmd in [
        "echo run5_drivers=$(ps aux | grep 'run_e0_flip_[r]erun' | wc -l); "
        "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader",
        "ls /root/mk_v2",
        "ls /root/mk_v2/phase1_details | wc -l; ls /root/mk_v2/phase1_details | head -3",
        "ls /root/mk_v2/best_kernels.json /root/mk_v2/runs 2>/dev/null | head -5",
        PY + " -c 'import pandas, pyarrow; print(pandas.__version__, pyarrow.__version__)' 2>&1 | tail -1",
        PY + " -c 'import pytest; print(pytest.__version__)' 2>&1 | tail -1",
        "ls /root/mk_v2/external /root/mk_v2/configs 2>/dev/null",
        "which compute-sanitizer; ls /usr/local/cuda/bin/compute-sanitizer 2>/dev/null",
        "ls /root/mk_v2_runs 2>/dev/null | tail -20",
        "for f in /root/mk_v2_runs/e0_run5*.log; do [ -f \"$f\" ] && echo \"--- $f\" && tail -2 \"$f\"; done",
        "wc -l /root/mk_v2_runs/e0_run5*/observations.jsonl 2>/dev/null",
    ]:
        print("### " + cmd)
        run(c, cmd, timeout=120)
elif step == "patch":
    print("### uploading patch")
    sftp = c.open_sftp()
    sftp.put("_e1_patch.tar.gz", "/root/mk_v2_e1_patch.tar.gz")
    sftp.close()
    run(c, "tar xzf /root/mk_v2_e1_patch.tar.gz -C /root/mk_v2 && echo PATCH_EXTRACTED")
    run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= " + PY + " -c \""
        "import sys; sys.path.insert(0, '.'); "
        "import scripts.run_e1_probe_study, scripts.extract_contracts, "
        "scripts.reconcile_corpora, scripts.run_e3_external, scripts.run_e1_cse_falsify; "
        "print('imports OK')\"")
elif step == "test":
    # CPU-only: torch-free unit tests + torch-CPU tests. run5 owns the GPU.
    run(c, "cd /root/mk_v2 && CUDA_VISIBLE_DEVICES= " + PY +
        " -m pytest tests -x -q 2>&1 | tail -15", timeout=1800)
elif step == "cmd":
    run(c, sys.argv[2], timeout=int(sys.argv[3]) if len(sys.argv) > 3 else 600)

c.close()
print("STEP_DONE:" + step)
