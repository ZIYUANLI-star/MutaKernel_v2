"""EMERGENCY: stop CSE lanes 3/4/5 + guard (pidfile + exact PIDs)."""
import _remote

c = _remote.connect()
print("===== stop guard =====")
_remote.run(c, "date '+%F %T %z'; GP=$(cat /root/mk_v2_runs/e1_guard.pid 2>/dev/null); "
               "echo guard_pid: $GP; kill -9 $GP 2>/dev/null; rm -f /root/mk_v2_runs/e1_guard.pid; "
               "pgrep -f e1_guard.sh | xargs -r kill -9; echo GUARD_STOPPED", timeout=30)

print("===== locate lanes 3/4/5 =====")
_, out, _ = _remote.run(c, "ps -eo pid,ppid,args", timeout=30, echo=False)
targets = []
for line in out.splitlines():
    if ("run_e1_cse_falsify.py" in line and "miniconda3/bin/python" in line
            and any(f"--lane {n}" in line for n in (3, 4, 5))):
        targets.append(int(line.split()[0]))
        print("driver:", line.strip()[:110])
for line in out.splitlines():
    parts = line.split()
    if "_mutant_worker.py" in line and len(parts) > 1 and \
            any(parts[1] == str(t) for t in targets):
        targets.append(int(parts[0]))
        print("worker:", line.strip()[:110])

print("===== kill =====")
if targets:
    _remote.run(c, f"kill -9 {' '.join(map(str, targets))} 2>/dev/null; sleep 2; "
                   "ps -eo args | grep -E 'run_e1_cse|_mutant_worker' | grep -v grep || echo STOPPED",
                timeout=30)
else:
    print("no lane 3/4/5 drivers found")
print("===== what did they write before the stop =====")
_remote.run(c, "for L in 3 4 5; do echo -n \"lane$L obs: \"; "
               "wc -l < /root/mk_v2_runs/e1/cse_observations_lane$L.jsonl 2>/dev/null || echo 0; done; "
               "nvidia-smi --query-gpu=memory.used --format=csv,noheader", timeout=30)
c.close()
print("STOP345_DONE")
