import _remote

c = _remote.connect()
cmds = [
    ("date/procs", "date '+%F %T %Z'; ps -eo pid,ppid,etime,rss,cmd | grep -E 'final_window|run_e1|_mutant_worker|_stress|sentinel' | grep -v grep"),
    ("gpu/mem/oom", "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; free -g | sed -n 2p; grep oom_kill /sys/fs/cgroup/memory/memory.oom_control"),
    ("fw_log_since_fire", "sed -n '/11:28:51 ] ========== FINAL WINDOW ORCHESTRATOR START/,$p' /root/mk_v2_runs/final_window.log"),
    ("markers", "ls -la /root/mk_v2_runs/e1/FINAL_WINDOW_DONE 2>&1; ls /root/mk_v2_runs/e1/ | grep -i requeue"),
    ("tagged_obs", "for f in /root/mk_v2_runs/e1/cse_observations_lane*p96* /root/mk_v2_runs/e1/cse_observations_lane*final_requeue* /root/mk_v2_runs/e1/cse_observations_lane*requeue*; do echo \"--- $f\"; wc -l < $f 2>/dev/null; done 2>/dev/null; ls -la /root/mk_v2_runs/e1/ | grep -E 'p96|requeue' "),
    ("archive", "wc -l /root/mk_v2_runs/e1/cse_observations_inc_archive_v2.jsonl; /root/miniconda3/bin/python -c \"import json; [print(json.loads(l)['probe_id']) for l in open('/root/mk_v2_runs/e1/cse_observations_inc_archive_v2.jsonl')]\""),
    ("ledgers", "for i in 3 5; do echo -n \"lane$i obs: \"; wc -l < /root/mk_v2_runs/e1/cse_observations_lane$i.jsonl; echo -n \"lane$i ledger: \"; /root/miniconda3/bin/python -c \"import json; print(len(json.load(open('/root/mk_v2_runs/e1/cse_completed_lane$i.json'))))\"; done"),
    ("review_dir", "ls -laR /root/mk_v2_runs/e1/final_window_review/ 2>/dev/null | head -60"),
    ("heartbeat", "tail -2 /root/mk_v2_runs/sentinel_heartbeat.jsonl"),
]
for name, cmd in cmds:
    print(f"\n===== {name} =====")
    code, o, e = _remote.run(c, cmd, timeout=120, echo=False)
    print(o.rstrip()[:13000])
    if e.strip():
        print("STDERR:", e[:600])
c.close()
print("\nPROBE_DONE")
