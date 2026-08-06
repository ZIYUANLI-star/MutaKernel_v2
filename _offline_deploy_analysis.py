"""Deploy the offline reuse analyzers to /root/mk_v2_runs/e1/analysis/ and
run the interim pass remotely (CPU-only; read-only over the run dir)."""
from pathlib import Path

from _remote import connect, run

ANALYSIS = "/root/mk_v2_runs/e1/analysis"
SCRIPTS = [
    "scripts/offline_reuse_lib.py",
    "scripts/offline_a1_crossfit_closure.py",
    "scripts/offline_a2_sole_detector.py",
    "scripts/offline_a3_budget_recall.py",
    "scripts/offline_a4_cost_c1.py",
    "scripts/offline_reuse_all.py",
]

client = connect()
run(client, f"mkdir -p {ANALYSIS}/scripts {ANALYSIS}/interim", timeout=30)
sftp = client.open_sftp()
for local in SCRIPTS:
    remote = f"{ANALYSIS}/scripts/{Path(local).name}"
    sftp.put(local, remote)
    print("PUT", remote)
sftp.close()

# interim pass on the remote copy of the data (lanes 1+2 default)
code, out, err = run(
    client,
    "cd /root/mk_v2 && MK_PROJECT_ROOT=/root/mk_v2 "
    f"/root/miniconda3/bin/python {ANALYSIS}/scripts/offline_reuse_all.py "
    f"--e1-dir /root/mk_v2_runs/e1 --out-dir {ANALYSIS}/interim",
    timeout=900)
run(client, f"ls -la {ANALYSIS}/interim", timeout=30)
client.close()
print("DEPLOY_DONE exit", code)
