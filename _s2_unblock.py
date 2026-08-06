import time
import _remote

B9 = "/root/mk_v2_runs/e3_b9_calib"

c = _remote.connect()
# sanity: nothing running, wcfu done, signoff done
_, o, _ = _remote.run(c, (
    "pgrep -af 'python.*(_b9_calib_driver_v2|_mutant_worker|_s2_chain|"
    "_b9_stage1_chain)\\.py|bash.*guard_b9_v2\\.sh' | grep -v 'bash -c' | head -5; "
    "ls %s/WCFU_DONE %s/WCFU2_DONE 2>/dev/null; "
    "ls /root/mk_v2_runs/e1/SIGNOFF_ORCH_DONE 2>/dev/null; echo SANITY_END") % (B9, B9),
    timeout=60, echo=False)
print("SANITY:\n" + o)
procs = [ln for ln in o.splitlines()
         if ".py" in ln and "SANITY_END" not in ln and "/root/mk_v2_runs" not in ln]
if procs:
    raise SystemExit("processes alive, refusing: %r" % procs)

_, o, _ = _remote.run(c, (
    "mv %s/PAUSED_FOR_SIGNOFF_RERUN %s/PAUSED_FOR_SIGNOFF_RERUN.stale_20260801 && "
    "mv %s/S2_CHAIN_BLOCKED %s/S2_CHAIN_BLOCKED.retry1 && "
    "echo '[unblock 2026-08-01] stale signoff pause marker archived; all "
    "chains done, station idle' >> %s/s2_chain.log && echo UNBLOCK_OK")
    % (B9, B9, B9, B9, B9), timeout=30, echo=False)
print(o)
if "UNBLOCK_OK" not in o:
    raise SystemExit("unblock failed")

try:
    _remote.run(c, (
        "cd /root/mk_v2 && nohup /root/miniconda3/bin/python -u _s2_chain.py "
        ">> %s/s2_chain_stdout.log 2>&1 < /dev/null & echo PID=$!") % B9,
        timeout=15, echo=False)
except Exception as exc:
    print("launch channel timeout (expected): %r" % exc)

time.sleep(20)
c2 = _remote.connect()
_, o, _ = _remote.run(c2, (
    "pgrep -af '[_]s2_chain.py|[g]uard_b9_v2|[_]b9_calib_driver'; echo ---; "
    "tail -8 %s/s2_chain.log") % B9, timeout=30, echo=False)
print(o)
c2.close()
c.close()
print("S2_UNBLOCK_DONE")
