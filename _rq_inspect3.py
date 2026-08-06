import _remote

c = _remote.connect()
CMDS = [
    "grep -n 'STRESS_POLICIES\\|stress_policies\\|POLICY\\|policy_bank' /root/mk_v2/scripts/run_e1_probe_study.py | head -20",
    "grep -n 'BASELINE_PROTOCOL\\|EQUIV_PROTOCOL\\|base_seed\\|equiv_runs\\|stress_repeats' /root/mk_v2/scripts/run_e1_probe_study.py | head -20",
    # what stress policies did production equiv/cse observations actually use?
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "from collections import Counter\n"
    "pol = Counter()\n"
    "for line in open('/root/mk_v2_runs/e1/equiv_observations.jsonl'):\n"
    "    r = json.loads(line)\n"
    "    for t in (r.get('trials') or []):\n"
    "        if t.get('round_type') == 'stress':\n"
    "            pol[t.get('policy')] += 1\n"
    "print('equiv stress policies:', dict(pol))\n"
    "pol2 = Counter()\n"
    "rec = None\n"
    "for line in open('/root/mk_v2_runs/e1/cse_observations_lane3.jsonl'):\n"
    "    r = json.loads(line)\n"
    "    if r.get('probe_id') == 'L1_P96__relop_replace__8':\n"
    "        rec = r\n"
    "    for t in (r.get('trials') or []):\n"
    "        if t.get('round_type') == 'stress':\n"
    "            pol2[t.get('policy')] += 1\n"
    "print('cse stress policies:', dict(pol2))\n"
    "if rec:\n"
    "    ts = rec.get('trials') or []\n"
    "    seq = [(t.get('round_type'), t.get('policy'), t.get('sub_index')) for t in ts]\n"
    "    print('P96 production trial count:', len(seq))\n"
    "    from collections import Counter as C\n"
    "    print('P96 stress policy multiset:', dict(C(p for rt, p, si in seq if rt=='stress')))\n"
    "    print('P96 cfg keys:', [k for k in rec.keys()][:20])\n"
    "    for k in ('base_seed','equiv_runs','stress_repeats','stress_policies','config'):\n"
    "        if k in rec:\n"
    "            print(' ', k, str(rec[k])[:200])\n"
    "EOF\n",
]
for cmd in CMDS:
    _, o, _ = _remote.run(c, cmd, timeout=90, echo=False)
    print(o)
    print('====')
c.close()
print('RQ_INSPECT3_DONE')
