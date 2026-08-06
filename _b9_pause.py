"""Pause B9 calibration to protect the critical-path CSE sign-off rerun.

B9's 4-lane concurrency (one unit peaked at ~79GB RSS) collided with the CSE
worker under the 120GiB cgroup cap and OOM-killed it (oom_kill 16 -> 18; the
#7 rerun died at 32/103 rounds).  B9 is preparatory work; the sign-off rerun
is the critical path, so B9 yields until it finishes.  Units are checkpointed
per unit, so killing mid-unit only costs the in-flight unit.
"""
import _remote

CMD = (
    # stop the guard first so it cannot restart the lanes
    "pkill -f 'guard_b9.sh' && echo GUARD_STOPPED; "
    "sleep 1; "
    "pkill -f '_b9_calib_driver.py' && echo DRIVERS_STOPPED; "
    "sleep 1; "
    "pkill -f 'run_e3_external.py run --plan /root/mk_v2_runs/e3_b9_calib' && echo UNITS_STOPPED; "
    "sleep 3; "
    "echo '--- remaining b9 procs ---'; "
    "ps aux | grep -E 'guard_b9|_b9_calib_driver|e3_b9_calib' | grep -v grep | wc -l; "
    "echo '--- gpu ---'; "
    "nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader; "
    "echo '--- cse worker (must survive) ---'; "
    "ps aux | grep '_mutant_[w]orker' | awk '{print $2,$3,$4,$12}'; "
    "echo '--- oom count ---'; "
    "grep oom_kill /sys/fs/cgroup/memory.events; "
    "echo '--- b9 progress preserved ---'; "
    "for f in /root/mk_v2_runs/e3_b9_calib/completed_lane*.json; do "
    "echo -n \"$f \"; /root/miniconda3/bin/python -c "
    "\"import json,sys; print(len(json.load(open(sys.argv[1]))))\" $f; done"
)

c = _remote.connect()
_remote.run(c, CMD, timeout=180)
sftp = c.open_sftp()
with sftp.open("/root/mk_v2_runs/e3_b9_calib/PAUSED_FOR_SIGNOFF_RERUN", "w") as f:
    f.write(
        "Paused 2026-07-30 ~16:58 CST: B9 4-lane concurrency OOM-killed the\n"
        "critical-path CSE sign-off rerun worker (oom_kill 16->18; #7 rerun\n"
        "died at 32/103 rounds).  Resume only after the sign-off rerun writes\n"
        "its last probe, and resume with reduced concurrency (<=2 lanes) plus\n"
        "a fix for the torch.quantile size limit that failed 10 units.\n")
sftp.close()
c.close()
print("B9_PAUSED")
