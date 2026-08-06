"""Launch the E1 equiv phase (survivor equivalence sifting) on the remote A800."""
import time
import _remote

c = _remote.connect()

env = ("PATH=/usr/local/cuda/bin:/root/miniconda3/bin:/usr/local/bin:/usr/bin:/bin "
       "TORCH_EXTENSIONS_DIR=/root/mk_v2_runs/torch_ext")
launch = (
    f"cd /root/mk_v2 && nohup env {env} /root/miniconda3/bin/python -u "
    "scripts/run_e1_probe_study.py --phase equiv --kernelbench-root KernelBench "
    "--out-dir /root/mk_v2_runs/e1 --timeout 420 "
    "> /root/mk_v2_runs/e1_equiv.log 2>&1 & echo LAUNCHED pid=$!"
)
_, out, _ = _remote.run(c, launch, timeout=60, echo=False)
print(out)

time.sleep(30)
_, out, _ = _remote.run(c, (
    "ps aux | grep 'run_e1_probe_[s]tudy' | grep -v grep; echo SEP; "
    "tail -c 1200 /root/mk_v2_runs/e1_equiv.log"
), timeout=60, echo=False)
c.close()
print(out)
print("EQUIV_LAUNCH_DONE")
