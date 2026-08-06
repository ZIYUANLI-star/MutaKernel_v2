"""Bring the A2/A4 evidence files back for the local record (A3 bookkeeping)."""
from pathlib import Path

import _remote

FILES = {
    "/root/_l3_a2_report.json": "_l3_a2_report.json",
    "/root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_draft_l3.freeze.json":
        "_contracts_c2c3c5_draft_l3.freeze.json",
    "/root/mk_v2_runs/e3_b9_calib/l3_scope/task_table.json":
        "_l3_scope_task_table.json",
}

c = _remote.connect()
sftp = c.open_sftp()
here = Path(__file__).resolve().parent
for remote, local in FILES.items():
    try:
        sftp.get(remote, str(here / local))
        print("fetched %-72s -> %s (%d bytes)"
              % (remote, local, (here / local).stat().st_size))
    except OSError as exc:
        print("MISSING %s (%s)" % (remote, exc))
sftp.close()
_remote.run(c, "ls -la /root/mk_v2_runs/e3_b9_calib/l3_scope/ && "
               "ls -la /root/mk_v2_runs/e2_reconcile/contracts_c2c3c5_draft*",
            timeout=180)
c.close()
