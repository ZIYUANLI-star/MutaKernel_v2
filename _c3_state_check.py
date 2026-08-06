"""Check remote C3 materialization state: parquets, candidates dir, pyarrow."""
import _remote as R

c = R.connect()
cmds = [
    "ls /root/mk_v2/external/ 2>/dev/null",
    "ls /root/mk_v2/external/C3_ai_cuda_engineer/ 2>/dev/null | head",
    "ls /root/mk_v2_runs/e2_reconcile/ | head -30",
    "ls /root/mk_v2_runs/e2_reconcile/C3/candidates/ 2>/dev/null | wc -l",
    "ls /root/mk_v2_runs/e2_reconcile/C3/ 2>/dev/null",
    "ls /root/mk_v2_runs/e3_corpora/ 2>/dev/null",
    "ls /root/mk_v2_runs/e3_campaign/ 2>/dev/null",
    "/root/miniconda3/bin/python -c 'import pyarrow; print(pyarrow.__version__)' 2>&1",
    # C5 wave1 upload state (verified earlier)
    "ls /root/mk_v2_runs/e3_corpora/c5_wave1/ 2>/dev/null | head -3; "
    "ls /root/mk_v2_runs/e3_corpora/c5_wave1/ 2>/dev/null | wc -l",
]
for cmd in cmds:
    print("### " + cmd)
    R.run(c, cmd, timeout=120)
c.close()
print("C3_STATE_DONE")
