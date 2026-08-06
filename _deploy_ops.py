import os
import _remote as R

FILES = [
    "build_wave15_lane_plans.py",
    "wave15_subset_analysis.py",
    "run_port_batch.py",
    "build_b9_tol_map.py",
    "wave15_orchestrator.py",
]

c = R.connect()
R.run(c, "mkdir -p /root/mk_v2_ops /root/mk_v2_runs/e3_campaign/wave15", timeout=30)
sftp = c.open_sftp()
for name in FILES:
    local = os.path.join("_ops_src", name)
    remote = f"/root/mk_v2_ops/{name}"
    sftp.put(local, remote)
    print("deployed", remote, os.path.getsize(local), "bytes")
sftp.close()
R.run(c, "cd /root/mk_v2 && git status --porcelain | wc -l", timeout=30)
c.close()
print("DEPLOY_DONE")
