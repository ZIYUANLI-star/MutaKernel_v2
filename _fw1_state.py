import _remote

c = _remote.connect()
for cmd in [
    # process states
    "ps -o pid,etime,args -p 200586 91971 108721 2>/dev/null",
    # done markers, exact names
    "ls -la /root/mk_v2_runs/e1/ | grep -i done",
    # lane3 remaining: plan vs completed
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "plan=json.load(open('/root/mk_v2_runs/e1/cse_lane_plan.json'))\n"
    "print('plan keys:', list(plan.keys())[:10] if isinstance(plan,dict) else type(plan))\n"
    "lane3=plan.get('3') or plan.get(3) or plan.get('lane3')\n"
    "comp=json.load(open('/root/mk_v2_runs/e1/cse_completed_lane3.json'))\n"
    "print('lane3 plan n=', len(lane3) if lane3 else None, 'completed type', type(comp), 'n=', len(comp))\n"
    "if lane3: print('remaining=', len([p for p in lane3 if p not in comp]))\n"
    "EOF",
    # lane3 log tail
    "tail -5 /root/mk_v2_runs/e1_cse_lane3.log",
    # obs counts
    "wc -l /root/mk_v2_runs/e1/cse_observations_lane*.jsonl 2>/dev/null; ls /root/mk_v2_runs/e1/cse_observations*archive* 2>/dev/null",
    # driver CLI
    "grep -n 'add_argument' /root/mk_v2/scripts/run_e1_cse_falsify.py",
    # probe study CLI
    "grep -n 'add_argument' /root/mk_v2/scripts/run_e1_probe_study.py | head -40",
    # policy skip file
    "cat /root/mk_v2_runs/e1/cse_policy_skip.json",
    # sentinel description
    "head -30 /root/mk_v2/e1_sentinel.py 2>/dev/null; ls /root/mk_v2/e1_sentinel.py /root/mk_v2_runs/e1_sentinel* 2>/dev/null",
]:
    print("### " + cmd.split("\n")[0][:80])
    _remote.run(c, cmd, timeout=120)
c.close()
print("FW1_DONE")
