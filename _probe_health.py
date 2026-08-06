import _remote

c = _remote.connect()
cmds = [
    ("hostname/uptime", "hostname; uptime; date '+%F %T %Z'"),
    ("processes", "ps -eo pid,ppid,etime,rss,cmd | grep -E 'cse|sentinel|guard|e1' | grep -v grep"),
    ("gpu", "nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu --format=csv"),
    ("gpu_procs", "nvidia-smi --query-compute-apps=pid,used_memory --format=csv"),
    ("mem/disk", "free -g; df -h /root | tail -1"),
    ("runs_dir", "ls -la /root/mk_v2_runs/ | head -60"),
    ("e1_dir", "ls -la /root/mk_v2_runs/e1/ | head -80"),
    ("lane_logs", "ls -la /root/mk_v2_runs/e1_cse_lane*.log 2>/dev/null; ls -la /root/mk_v2_runs/*.log 2>/dev/null | head -30"),
    ("heartbeat_tail", "tail -5 /root/mk_v2_runs/sentinel_heartbeat.jsonl 2>/dev/null"),
    ("dmesg_oom", "dmesg -T 2>/dev/null | grep -iE 'oom|killed process' | tail -10"),
]
for name, cmd in cmds:
    print(f"\n===== {name} =====")
    code, o, e = _remote.run(c, cmd, timeout=120, echo=False)
    if o.strip():
        print(o.rstrip())
    if e.strip():
        print("STDERR:", e.rstrip()[:1500])
    if code != 0:
        print("EXIT:", code)
c.close()
print("\nPROBE_DONE")
