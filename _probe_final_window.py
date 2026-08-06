import _remote

c = _remote.connect()
cmds = [
    ("date/procs", "date '+%F %T %Z'; ps -eo pid,ppid,etime,rss,cmd | grep -E 'cse|sentinel|guard|final_window|_mutant_worker' | grep -v grep"),
    ("gpu/mem", "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; free -g | sed -n 2p"),
    ("markers", "ls -la /root/mk_v2_runs/e1/CSE_DONE* /root/mk_v2_runs/e1/FINAL_WINDOW_DONE 2>&1"),
    ("lane3_log_tail", "tail -12 /root/mk_v2_runs/e1_cse_lane3.log"),
    ("fw_log", "cat /root/mk_v2_runs/final_window.log | tail -80"),
    ("fw_trigger_log", "tail -6 /root/mk_v2_runs/final_window_trigger.log"),
    ("fw_review_dir", "ls -laR /root/mk_v2_runs/e1/final_window_review/ 2>/dev/null | head -40"),
    ("archives", "ls -la /root/mk_v2_runs/e1/ | grep -iE 'final|archive|bak_final|requeue' | head -20"),
    ("obs_counts", "for f in /root/mk_v2_runs/e1/cse_observations_lane[0-5].jsonl; do echo -n \"$f : \"; wc -l < $f; done"),
    ("oom", "cat /sys/fs/cgroup/memory/memory.oom_control; dmesg -T 2>/dev/null | grep -iE 'oom|killed' | tail -5"),
    ("heartbeat", "tail -3 /root/mk_v2_runs/sentinel_heartbeat.jsonl"),
    ("sentinel_tail", "tail -6 /root/mk_v2_runs/e1_sentinel.log"),
]
for name, cmd in cmds:
    print(f"\n===== {name} =====")
    code, o, e = _remote.run(c, cmd, timeout=120, echo=False)
    print(o.rstrip()[:9000])
    if e.strip():
        print("STDERR:", e[:600])
c.close()
print("\nPROBE_DONE")
