import _remote

c = _remote.connect()
cmds = [
    ("guard_restarts", "grep -c 'AUTORESTART' /root/mk_v2_runs/e1_cse_lane3.log; grep -c 'AUTORESTART' /root/mk_v2_runs/e1_cse_lane4.log; grep -c 'AUTORESTART' /root/mk_v2_runs/e1_cse_lane5.log"),
    ("restart_lines", "grep -h 'AUTORESTART\\|LAUNCH' /root/mk_v2_runs/e1_cse_lane[345].log"),
    ("policy_skip", "cat /root/mk_v2_runs/e1/cse_policy_skip.json"),
    ("lane_sizes", """/root/miniconda3/bin/python - <<'EOF'
import json
p = json.load(open('/root/mk_v2_runs/e1/cse_lane_plan.json'))
print('top keys:', list(p.keys()))
for k, v in p.items():
    if isinstance(v, dict) and k not in ('kernel_stats', 'vram_classification'):
        print(k, {kk: (len(vv) if isinstance(vv, list) else vv) for kk, vv in list(v.items())[:12]})
    elif isinstance(v, list):
        print(k, 'list len', len(v))
EOF"""),
    ("lane5_head", "head -20 /root/mk_v2_runs/e1_cse_lane5.log"),
    ("worker_now", "ps -eo pid,etimes,cmd | grep _mutant_worker | grep -v grep"),
]
for name, cmd in cmds:
    print(f"\n===== {name} =====")
    code, o, e = _remote.run(c, cmd, timeout=120, echo=False)
    if o.strip():
        print(o.rstrip()[:6000])
    if e.strip():
        print("STDERR:", e.rstrip()[:1000])
c.close()
print("\nPROBE_DONE")
