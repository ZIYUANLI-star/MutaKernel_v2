"""Run the final offline reuse analysis on remote (CPU-only, post-amendment)."""
import _remote

c = _remote.connect()
cmd = (
    "MK_PROJECT_ROOT=/root/mk_v2 /root/miniconda3/bin/python "
    "/root/mk_v2_runs/e1/analysis/scripts/offline_reuse_all.py "
    "--e1-dir /root/mk_v2_runs/e1 "
    "--out-dir /root/mk_v2_runs/e1/analysis/final "
    "--cse-obs '/root/mk_v2_runs/e1/cse_observations_lane*.jsonl' --final"
)
_, o, e = _remote.run(c, cmd, timeout=1800, echo=False)
print(o)
if e.strip():
    print("STDERR:\n" + e[-3000:])
_, o, _ = _remote.run(c, "ls -la /root/mk_v2_runs/e1/analysis/final/ | head -30",
                      timeout=30, echo=False)
print(o)
c.close()
