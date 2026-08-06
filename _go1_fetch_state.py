#!/usr/bin/env python3
"""Step 1 (read-only): fetch running code, guard, cgroup memory account."""
import _remote

c = _remote.connect()
sftp = c.open_sftp()
for remote, local in [
    ("/root/mk_v2/scripts/_mutant_worker.py", "_rt_mutant_worker.py"),
    ("/root/mk_v2/scripts/run_e1_cse_falsify.py", "_rt_run_e1_cse_falsify.py"),
]:
    sftp.get(remote, local)
sftp.close()

CMDS = [
    ("md5 remote vs known", "md5sum /root/mk_v2/scripts/_mutant_worker.py "
     "/root/mk_v2/scripts/run_e1_cse_falsify.py /root/mk_v2/src/stress/policy_bank.py "
     "/root/mk_v2/scripts/run_e1_probe_study.py"),
    ("WORKER_CORRECTED", "grep -n 'WORKER_CORRECTED' /root/mk_v2/scripts/run_e1_probe_study.py"),
    ("guard file", "ls -la /root/mk_v2_runs/e1_guard_cse_split.sh 2>/dev/null; "
     "ls /root/mk_v2_runs/*.sh 2>/dev/null"),
    ("guard procs", "ps -eo pid,etime,args | grep -E 'guard' | grep -v grep"),
    ("driver+worker procs", "ps -eo pid,ppid,etime,%cpu,rss,args --sort=-rss | "
     "grep -E 'run_e1_cse|_mutant_worker' | grep -v grep"),
    ("worker cgroup", "for p in $(pgrep -f _mutant_worker.py); do echo PID $p; cat /proc/$p/cgroup; done"),
    ("cgroup mem", "cat /sys/fs/cgroup/memory.max 2>/dev/null; cat /sys/fs/cgroup/memory.current 2>/dev/null; "
     "cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null; "
     "cat /sys/fs/cgroup/memory/memory.usage_in_bytes 2>/dev/null"),
    ("host mem", "free -g"),
    ("obs mtimes", "ls -la --time-style=+%H:%M:%S /root/mk_v2_runs/e1/cse_observations_lane3.jsonl "
     "/root/mk_v2_runs/e1/cse_observations_lane4.jsonl /root/mk_v2_runs/e1/cse_completed_lane3.json "
     "/root/mk_v2_runs/e1/cse_completed_lane4.json"),
    ("tests dir", "ls /root/mk_v2/tests/ | head -30"),
]
for title, cmd in CMDS:
    print("=" * 12, title)
    code, o, e = _remote.run(c, cmd, timeout=120, echo=False)
    print(o.rstrip()[:3500])
    if e.strip():
        print("STDERR:", e.strip()[:400])
c.close()
print("FETCH_DONE")
