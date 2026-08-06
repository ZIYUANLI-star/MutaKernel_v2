"""Inspect canary failure reasons + why 6 PENDING_CONTROL remain + fix wave liveness."""
import _remote

CMD1 = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "from collections import Counter\n"
    "p = '/root/mk_v2_runs/e3_b9_calib/wcfu_canary/b9_L2_P14_observations.jsonl'\n"
    "recs = [json.loads(l) for l in open(p) if l.strip()]\n"
    "reasons = Counter(str(r.get('reason'))[:70] for r in recs)\n"
    "print('canary reasons:', dict(reasons))\n"
    "has_b9 = sum(1 for r in recs if isinstance(r.get('b9'), dict) and r['b9'].get('max_abs_err') is not None)\n"
    "print('records with finite b9.max_abs_err:', has_b9, '/', len(recs))\n"
    "if recs and recs[0].get('b9'):\n"
    "    print('sample b9:', json.dumps(recs[0]['b9']))\n"
    "    print('sample tol:', recs[0].get('calibrated_tol'))\n"
    "EOF\n"
)

CMD2 = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "j = json.load(open('/root/mk_v2_runs/e1/witness_confirmation/wc1_report.json'))\n"
    "kd = j['kernel_determinism']\n"
    "for k in ('L1_P49', 'L2_P68', 'L2_P81', 'L1_P39'):\n"
    "    e = kd.get(k)\n"
    "    if e:\n"
    "        for pos in e['positions']:\n"
    "            print(k, pos['stage'], pos['position'], pos['cell_state'],\n"
    "                  'pass', pos['pass_rounds'], 'fail', pos['fail_rounds'])\n"
    "EOF\n"
)

CMD3 = (
    "pgrep -af '[_]b9_calib_driver_v2' | head; echo SEP; "
    "/root/miniconda3/bin/python -c \"import json; qs=json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json')); print('done', len(qs['done']), 'pending', len(qs['pending']), 'claimed', list(qs.get('claimed', {}).keys()))\"; echo SEP; "
    "grep 'fp16\\|start \\|calibrated\\|controls_incomplete' /root/mk_v2_runs/e3_b9_calib/lane_v2_0.log | tail -4; echo '---'; "
    "grep 'start \\|calibrated\\|controls_incomplete' /root/mk_v2_runs/e3_b9_calib/lane_v2_1.log | tail -4"
)

c = _remote.connect()
print('##### canary #####')
_, o, _ = _remote.run(c, CMD1, timeout=90, echo=False)
print(o)
print('##### pending control rounds #####')
_, o, _ = _remote.run(c, CMD2, timeout=90, echo=False)
print(o)
print('##### fix wave #####')
_, o, _ = _remote.run(c, CMD3, timeout=90, echo=False)
c.close()
print(o)
print('CANARY_PENDING_DONE')
