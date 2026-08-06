import _remote

SCRIPT = r"""
import json, datetime
# heartbeat mem around 20:30-21:10 CST (12:30-13:10 UTC)
for ln in open('/root/mk_v2_runs/sentinel_heartbeat.jsonl'):
    h = json.loads(ln)
    if '2026-07-28T20:2' <= h['at'][:13+2] <= '2026-07-28T21:2':
        print(h['at'], 'host_mem=', h['mem_used_gb'], 'gpu=', h['gpu_mem_used_mib'], 'oom_lines=', h['oom_kill_lines'], 'actions=', h['actions'])
"""

c = _remote.connect()
code, o, e = _remote.run(c, "/root/miniconda3/bin/python - <<'PYEOF'\n" + SCRIPT + "\nPYEOF", timeout=120, echo=False)
print("== heartbeat 20:20-21:20 ==")
print(o)
if e.strip():
    print("STDERR:", e[:800])

for name, cmd in [
    ("worker_log", "tail -40 /root/mk_v2_runs/e1/worker_logs/L1_P52__arith_replace__11_equiv.log"),
    ("worker_logs_dir", "ls -la /root/mk_v2_runs/e1/worker_logs/ | tail -15"),
    ("lane3_log_2050_2110", "grep -n '2026-07-28T12:5\\|2026-07-28 20:5\\|2026-07-28 21:0\\|worker\\|died\\|exit\\|signal\\|kill' /root/mk_v2_runs/e1_cse_lane3.log | tail -15"),
    ("driver_grade_inc", "grep -n 'other_unknown\\|partial_result\\|worker' /root/mk_v2/scripts/run_e1_cse_falsify.py | head -25"),
    ("cgroup_oom_check", "cat /sys/fs/cgroup/memory/memory.oom_control 2>/dev/null; cat /sys/fs/cgroup/memory.events 2>/dev/null; cat /sys/fs/cgroup/memory/memory.failcnt 2>/dev/null"),
]:
    print(f"\n===== {name} =====")
    code, o, e = _remote.run(c, cmd, timeout=60, echo=False)
    print(o.rstrip()[:4000])
    if e.strip():
        print("STDERR:", e[:500])
c.close()
