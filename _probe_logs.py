import _remote

c = _remote.connect()
cmds = [
    ("lane3_tail", "tail -25 /root/mk_v2_runs/e1_cse_lane3.log"),
    ("lane4_tail", "tail -25 /root/mk_v2_runs/e1_cse_lane4.log"),
    ("lane5_tail", "tail -15 /root/mk_v2_runs/e1_cse_lane5.log"),
    ("errors_345", "for f in 3 4 5; do echo '--- lane'$f; tail -c 200000 /root/mk_v2_runs/e1_cse_lane$f.log | grep -inE 'error|oom|killed|traceback' | tail -10; done"),
    ("sentinel_log_tail", "tail -30 /root/mk_v2_runs/e1_sentinel.log"),
    ("sentinel_state", "cat /root/mk_v2_runs/e1_sentinel_state.json"),
    ("guard_script_head", "head -50 /root/mk_v2_runs/e1_guard_cse_split.sh"),
    ("guard_restarts", "grep -c AUTORESTART /root/mk_v2_runs/e1_cse_lane3.log /root/mk_v2_runs/e1_cse_lane4.log /root/mk_v2_runs/e1_cse_lane5.log 2>/dev/null; grep -i 'restart' /root/mk_v2_runs/e1_cse_lane[345].log | tail -12"),
    ("policy_skip", "cat /root/mk_v2_runs/e1/cse_policy_skip.json"),
    ("lane_plan_counts", "/root/miniconda3/bin/python -c \"import json; p=json.load(open('/root/mk_v2_runs/e1/cse_lane_plan.json')); print(type(p)); print({k:(len(v) if isinstance(v,list) else v) for k,v in p.items()} if isinstance(p,dict) else len(p))\""),
    ("completed_counts", "for f in /root/mk_v2_runs/e1/cse_completed_lane*.json; do echo -n \"$f : \"; /root/miniconda3/bin/python -c \"import json,sys; d=json.load(open('$f')); print(len(d) if isinstance(d,(list,dict)) else d)\"; done"),
    ("obs_counts", "for f in /root/mk_v2_runs/e1/cse_observations_lane[0-5].jsonl; do echo -n \"$f : \"; wc -l < $f; done"),
    ("heartbeat_count", "wc -l /root/mk_v2_runs/sentinel_heartbeat.jsonl"),
]
for name, cmd in cmds:
    print(f"\n===== {name} =====")
    code, o, e = _remote.run(c, cmd, timeout=120, echo=False)
    if o.strip():
        print(o.rstrip())
    if e.strip():
        print("STDERR:", e.rstrip()[:1500])
c.close()
print("\nPROBE_DONE")
