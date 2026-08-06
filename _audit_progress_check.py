"""Confirm the followup audit is actually executing on GPU."""
import time
import _remote

CMD = (
    "date '+%T'; "
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; echo GPUEND; "
    "tail -n 6 /root/mk_v2_runs/e1/witness_confirmation/audit_lane0.log; echo SEP; "
    "ls /root/mk_v2_runs/e3_b9_calib/brakes/ 2>/dev/null; "
    "ls /root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN 2>/dev/null && echo PAUSEMARKER_OK"
)

c = _remote.connect()
for i in range(2):
    _, o, _ = _remote.run(c, CMD, timeout=90, echo=False)
    print("== poll %d ==" % i)
    print(o)
    if i == 0:
        time.sleep(90)
c.close()
print("AUDIT_CHECK_DONE")
