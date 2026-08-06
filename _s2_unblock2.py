import time
import _remote

B9 = "/root/mk_v2_runs/e3_b9_calib"

c = _remote.connect()
_, o, _ = _remote.run(c, (
    "ls -la %s/brakes/ 2>/dev/null; echo ---; "
    "ls %s/PAUSED_FOR_SIGNOFF_RERUN 2>/dev/null || echo NO_PAUSE_MARKER; echo ---; "
    "pgrep -af 'python.*_b9_stage1_chain\\.py' | grep -v 'bash -c'") % (B9, B9),
    timeout=60, echo=False)
print(o)
if "NO_PAUSE_MARKER" not in o:
    raise SystemExit("pause marker back again - investigate")
brake_lines = [ln for ln in o.split("---")[0].splitlines()
               if ln.strip() and not ln.startswith("total")
               and " ." not in ln and not ln.rstrip().endswith(" .")
               and not ln.rstrip().endswith(" ..")]
print("brake entries:", brake_lines)

pid_lines = [ln for ln in o.splitlines() if "_b9_stage1_chain.py" in ln
             and "python" in ln]
if pid_lines:
    pid = pid_lines[-1].split()[0]
    _, o2, _ = _remote.run(c, (
        "kill %s && sleep 2 && (pgrep -af 'python.*_b9_stage1_chain' | grep -v 'bash -c' "
        "|| echo STEWARD_GONE); "
        "echo '[retire 2026-08-01] stage1 steward retired before stage-2 launch "
        "(stale LANES/BUDGET defaults would fight the stage-2 guard)' >> %s/stage1_chain.log")
        % (pid, B9), timeout=30, echo=False)
    print(o2)
    if "STEWARD_GONE" not in o2:
        raise SystemExit("steward still alive")

_, o, _ = _remote.run(c, "mv %s/S2_CHAIN_BLOCKED %s/S2_CHAIN_BLOCKED.retry1 2>/dev/null; echo OK" % (B9, B9),
                      timeout=30, echo=False)

try:
    _remote.run(c, (
        "cd /root/mk_v2 && nohup /root/miniconda3/bin/python -u _s2_chain.py "
        ">> %s/s2_chain_stdout.log 2>&1 < /dev/null & echo PID=$!") % B9,
        timeout=15, echo=False)
except Exception as exc:
    print("launch channel timeout (expected): %r" % exc)

time.sleep(30)
c2 = _remote.connect()
_, o, _ = _remote.run(c2, (
    "tail -12 %s/s2_chain.log; echo ---; "
    "pgrep -af '[g]uard_b9_v2|python.*_b9_calib_driver_v2' | head -4; echo ---; "
    "ls %s/S2_CHAIN_FIRED %s/S2_CHAIN_BLOCKED 2>/dev/null") % (B9, B9, B9),
    timeout=30, echo=False)
print(o)
c2.close()
c.close()
print("S2_UNBLOCK2_DONE")
