"""Advisor decision groundwork: pull WC-1 final report, audit tooling, dtype code path."""
import _remote

CMD1 = (
    "ls /root/mk_v2_runs/e1/witness_confirmation/; echo SEP; "
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json, glob\n"
    "cands = sorted(glob.glob('/root/mk_v2_runs/e1/witness_confirmation/*report*.json'))\n"
    "print('report files:', cands)\n"
    "p = cands[-1] if cands else None\n"
    "if p:\n"
    "    j = json.load(open(p))\n"
    "    print('top keys:', list(j.keys()))\n"
    "    v = j.get('verdicts') or j.get('witness_verdicts') or {}\n"
    "    if isinstance(v, dict):\n"
    "        from collections import Counter\n"
    "        c = Counter(x.get('verdict') if isinstance(x, dict) else str(x) for x in v.values())\n"
    "        print('verdict counts:', dict(c))\n"
    "        for k, x in v.items():\n"
    "            vd = x.get('verdict') if isinstance(x, dict) else str(x)\n"
    "            if vd != 'CONFIRMED':\n"
    "                print(' ', vd, k, json.dumps(x, ensure_ascii=False)[:220] if isinstance(x, dict) else '')\n"
    "    else:\n"
    "        print(json.dumps(j, ensure_ascii=False)[:3000])\n"
    "EOF\n"
)

CMD2 = (
    "ls /root/mk_v2/ | grep -iE 'wc|audit|requeue|confirm' ; echo SEP; "
    "ls /root/mk_v2_runs/e1/witness_confirmation/cells/ | head -30; echo SEP; "
    "head -c 1200 /root/mk_v2_runs/e1/witness_confirmation/plan.json"
)

CMD3 = (
    "grep -rn 'float16\\|half()\\|\\.half\\b' /root/mk_v2/scripts/run_e3_external.py | head -20; echo SEP; "
    "grep -rln 'float16' /root/mk_v2/*.py | head; echo SEP; "
    "grep -n 'dtype' /root/mk_v2/_b9_make_units.py 2>/dev/null | head; "
    "ls /root/mk_v2/ | grep -i b9"
)

c = _remote.connect()
print('##### WC REPORT #####')
_, o, _ = _remote.run(c, CMD1, timeout=180, echo=False)
print(o)
print('##### WC TOOLING #####')
_, o, _ = _remote.run(c, CMD2, timeout=120, echo=False)
print(o)
print('##### DTYPE PATH #####')
_, o, _ = _remote.run(c, CMD3, timeout=120, echo=False)
c.close()
print(o)
print('ADV_INSPECT_DONE')
