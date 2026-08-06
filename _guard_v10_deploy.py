"""Guard v10 rollout, pidfile discipline: syntax-check the new script first,
stop the running guard (drivers untouched), back up v9, install v10, restart,
verify pidfile/drivers, and print the new progress line's INC counts once."""
import time

import _remote

c = _remote.connect()
sftp = c.open_sftp()
sftp.put("_guard_v10.sh", "/root/mk_v2_runs/e1_guard_cse_split_v10.sh")
print("PUT guard v10")
sftp.close()

print("===== 0. strip CRLF + syntax check BEFORE touching anything =====")
code, _, _ = _remote.run(c, "sed -i 's/\\r$//' /root/mk_v2_runs/e1_guard_cse_split_v10.sh && "
                            "bash -n /root/mk_v2_runs/e1_guard_cse_split_v10.sh "
                            "&& echo SYNTAX_OK", timeout=30)
if code != 0:
    raise SystemExit("ABORT: v10 syntax check failed")

print("===== 1. snapshot drivers (must be identical after) =====")
_, before, _ = _remote.run(
    c, "ps -eo pid,args | grep 'run_e1_cse_[f]alsify' | awk '{print $1, $NF}'",
    timeout=30)

print("===== 2. stop guard via pidfile =====")
_remote.run(c, "GP=$(cat /root/mk_v2_runs/e1_guard.pid 2>/dev/null); "
               "echo guard_pid: $GP; kill -9 $GP 2>/dev/null; "
               "rm -f /root/mk_v2_runs/e1_guard.pid; sleep 1; "
               "pgrep -f e1_guard_cse_split >/dev/null && echo STILL_ALIVE "
               "|| echo GUARD_STOPPED", timeout=30)

print("===== 3. back up v9, install v10 =====")
_remote.run(c, "cp /root/mk_v2_runs/e1_guard_cse_split.sh "
               "/root/mk_v2_runs/e1_guard_cse_split_v9.bak.sh && "
               "cp /root/mk_v2_runs/e1_guard_cse_split_v10.sh "
               "/root/mk_v2_runs/e1_guard_cse_split.sh && "
               "chmod +x /root/mk_v2_runs/e1_guard_cse_split.sh && "
               "echo INSTALLED", timeout=30)

print("===== 4. restart guard =====")
try:
    _remote.run(c, "nohup /root/mk_v2_runs/e1_guard_cse_split.sh "
                   ">/dev/null 2>&1 & sleep 3; "
                   "cat /root/mk_v2_runs/e1_guard.pid", timeout=15)
except Exception as exc:
    print("guard launch (tolerated):", type(exc).__name__)
time.sleep(5)

print("===== 5. verify =====")
_remote.run(c, "cat /root/mk_v2_runs/e1_guard.pid; "
               "ps -eo pid,args | grep 'e1_guard_cse_[s]plit' ", timeout=30)
_, after, _ = _remote.run(
    c, "ps -eo pid,args | grep 'run_e1_cse_[f]alsify' | awk '{print $1, $NF}'",
    timeout=30)
print("drivers unchanged:", sorted(before.split()) == sorted(after.split()))
_remote.run(c, "grep GUARD_STARTED /root/mk_v2_runs/e1_cse_lane3.log | tail -1",
            timeout=30)

print("===== 6. one-shot progress-line dry run (same command as v10) =====")
_remote.run(c, 'for L in 3 4 5; do OBS=/root/mk_v2_runs/e1/cse_observations_lane$L.jsonl; '
               'N=$(wc -l < "$OBS" 2>/dev/null || echo 0); '
               'I=$(grep -c \'"outcome": "INCONCLUSIVE"\' "$OBS" 2>/dev/null); I=${I:-0}; '
               'echo "lane $L obs=$N inconclusive=$I"; done', timeout=30)
c.close()
print("GUARD_V10_DEPLOY_DONE")
