"""Inspect worker invocation machinery + production configs for the 7 requeue probes."""
import _remote

CMD1 = "sed -n '396,460p' /root/mk_v2/_wc_audit.py"
CMD2 = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "inv = json.load(open('/root/mk_v2_runs/e1/_wc_witness_inventory.json'))\n"
    "print(type(inv).__name__, len(inv))\n"
    "items = inv if isinstance(inv, list) else inv.get('witnesses', [])\n"
    "if isinstance(inv, dict):\n"
    "    print('keys:', list(inv.keys()))\n"
    "targets = ('L1_P37__const_perturb__2', 'L1_P37__const_perturb__3', 'L1_P37__const_perturb__7',\n"
    "           'L1_P37__mask_boundary__0', 'L1_P49__sync_remove__0', 'L2_P63__sync_remove__1',\n"
    "           'L1_P96__relop_replace__8')\n"
    "for it in (items if isinstance(items, list) else []):\n"
    "    if isinstance(it, dict) and it.get('probe_id') in targets:\n"
    "        print(json.dumps(it, ensure_ascii=False)[:400])\n"
    "EOF\n"
)
CMD3 = (
    "grep -n 'def worker_cmd\\|_mutant_worker\\|--probe\\|--config\\|subprocess' /root/mk_v2/_wc_audit.py | head -15; echo SEP; "
    "ls /root/mk_v2/scripts/ | grep -i worker; echo SEP; "
    "/root/miniconda3/bin/python -c \"\n"
    "import json\n"
    "d=json.load(open('/root/mk_v2_runs/e1/cse_lane_plan.json'))\n"
    "print(type(d).__name__, list(d)[:6] if isinstance(d, dict) else len(d))\" 2>/dev/null; echo SEP; "
    "grep -rn 'stress_policies' /root/mk_v2/_wc_audit.py | head -8"
)

c = _remote.connect()
print('##### run_cells 396-460 #####')
_, o, _ = _remote.run(c, CMD1, timeout=60, echo=False)
print(o)
print('##### witness inventory entries #####')
_, o, _ = _remote.run(c, CMD2, timeout=60, echo=False)
print(o)
print('##### worker plumbing #####')
_, o, _ = _remote.run(c, CMD3, timeout=60, echo=False)
c.close()
print(o)
print('RQ_INSPECT_DONE')
