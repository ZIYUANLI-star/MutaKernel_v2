import _remote

c = _remote.connect()
CMDS = [
    "sed -n '60,100p' /root/mk_v2/scripts/run_e1_probe_study.py",
    "sed -n '400,500p' /root/mk_v2/scripts/run_e1_probe_study.py",
    # probe file structure: what fields does each probe carry?
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import sys, json\n"
    "sys.path.insert(0, '/root/mk_v2')\n"
    "import scripts.run_e1_probe_study as ps\n"
    "from pathlib import Path\n"
    "pf = ps._load_probe_files(Path('/root/mk_v2_runs/e1'))\n"
    "targets = {'L1_P37__const_perturb__2','L1_P37__const_perturb__3','L1_P37__const_perturb__7',\n"
    "           'L1_P37__mask_boundary__0','L1_P49__sync_remove__0','L2_P63__sync_remove__1',\n"
    "           'L1_P96__relop_replace__8'}\n"
    "print('EQUIV_RUNS', ps.EQUIV_RUNS, 'BASE_SEED', ps.EQUIV_BASE_SEED)\n"
    "print('protocol', {k: v for k, v in ps.BASELINE_PROTOCOL.items() if k != 'notes'})\n"
    "for kf in pf:\n"
    "    for p in kf['probes']:\n"
    "        if p['probe_id'] in targets:\n"
    "            keys = list(p.keys())\n"
    "            print(p['probe_id'], 'keys:', keys)\n"
    "            for k in ('stress_policies','policies','selected_policies','policy_plan'):\n"
    "                if k in p:\n"
    "                    print('   ', k, '=', p[k])\n"
    "EOF\n",
]
for cmd in CMDS:
    _, o, _ = _remote.run(c, cmd, timeout=90, echo=False)
    print(o)
    print('====')
c.close()
print('RQ_INSPECT4_DONE')
