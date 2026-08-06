"""Second-round diagnosis: container restart vs cgroup OOM vs silent kill."""
import _remote

CMDS = [
    ("pid1", "stat -c 'pid1 changed: %y' /proc/1; ps -o pid,lstart,cmd -p 1"),
    ("oldest_procs", "ps -eo pid,lstart,etime,cmd --sort=start_time | head -12"),
    ("cgroup_v2", "cat /sys/fs/cgroup/memory.events 2>/dev/null; echo ---; "
                  "cat /sys/fs/cgroup/memory.max 2>/dev/null"),
    ("cgroup_v1", "cat /sys/fs/cgroup/memory/memory.oom_control 2>/dev/null; echo ---; "
                  "cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null; echo ---; "
                  "cat /sys/fs/cgroup/memory/memory.failcnt 2>/dev/null"),
    ("scratch", "ls -la /root/mk_v2_runs/e1/ | grep e1eq; echo ---; "
                "for d in /root/mk_v2_runs/e1/e1eq_*; do ls -la $d; done 2>/dev/null | head -20"),
    ("scratch_cfg", "cat /root/mk_v2_runs/e1/e1eq_*/cfg_*.json 2>/dev/null | "
                    "/root/miniconda3/bin/python -c \"import sys,json; d=json.load(sys.stdin); print(d.get('mutant_id'), d.get('operator_name'))\" 2>/dev/null "
                    "|| echo NO_LEFTOVER_CFG"),
    ("worker_logs", "ls -lat /root/mk_v2_runs/e1/worker_logs/ 2>/dev/null | head -8"),
    ("bash_hist", "grep -n 'run_e1_probe_study' /root/.bash_history 2>/dev/null | tail -5 || echo NO_HIST"),
    ("dmesg_perm", "dmesg 2>&1 | head -2"),
    ("obs_first_ts", "head -n 1 /root/mk_v2_runs/e1/equiv_observations.jsonl | /root/miniconda3/bin/python -c \"import sys,json; r=json.loads(sys.stdin.read()); print(r['probe_id'], r['finished_at'])\""),
    ("obs_last3_ts", "tail -n 3 /root/mk_v2_runs/e1/equiv_observations.jsonl | /root/miniconda3/bin/python -c \"import sys; [print(__import__('json').loads(l)['probe_id'], __import__('json').loads(l)['finished_at'], __import__('json').loads(l)['wall_ms']) for l in sys.stdin]\""),
]

c = _remote.connect()
for name, cmd in CMDS:
    print(f"===== {name} =====")
    try:
        _remote.run(c, cmd, timeout=60)
    except Exception as exc:
        print("CMD_ERROR:", exc)
c.close()
print("DEATHCHECK2_DONE")
