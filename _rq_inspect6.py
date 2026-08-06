import _remote

c = _remote.connect()
CMDS = [
    # 1) worker directed-policy selection
    "grep -n 'def .*polic\\|DIRECTED\\|directed' /root/mk_v2/scripts/_mutant_worker.py | head -20",
    # 2) final wc1_report regrade plan + verdicts for our 7 probes
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json, glob\n"
    "rep = json.load(open('/root/mk_v2_runs/e1/witness_confirmation/wc1_report.json'))\n"
    "print('generated_at:', rep.get('generated_at'))\n"
    "plan = rep.get('regrade_plan') or []\n"
    "for it in plan:\n"
    "    print(json.dumps(it, ensure_ascii=False)[:260])\n"
    "EOF\n",
    # 3) cse manifest: all_policies + policy_skip for L1_P96
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json, glob\n"
    "for mf in sorted(glob.glob('/root/mk_v2_runs/e1/cse_manifest*.json')):\n"
    "    m = json.load(open(mf))\n"
    "    s = m.get('search', {})\n"
    "    print(mf, '->', len(s.get('stress_policies') or []), 'policies')\n"
    "    print('  policies:', s.get('stress_policies'))\n"
    "    ps = m.get('policy_skip') or {}\n"
    "    hits = {k: v for k, v in ps.items() if 'P96' in k or '96' in k}\n"
    "    print('  skip entries:', len(ps), 'P96-related:', hits)\n"
    "    break\n"
    "EOF\n",
    "ls /root/mk_v2_runs/e1/ | grep -i 'cse.*manifest\\|manifest.*cse'",
]
for cmd in CMDS:
    _, o, e = _remote.run(c, cmd, timeout=90, echo=False)
    print(o)
    if e.strip():
        print('STDERR:', e[:500])
    print('====')
c.close()
print('RQ_INSPECT6_DONE')
