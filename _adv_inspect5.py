"""Last details: --only semantics, verdict schema, stage1_chain loop end."""
import _remote

CMD1 = "sed -n '491,545p' /root/mk_v2/_wc_audit.py"
CMD2 = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json\n"
    "j = json.load(open('/root/mk_v2_runs/e1/witness_confirmation/wc1_report.json'))\n"
    "v = j['verdicts']\n"
    "print(type(v).__name__, len(v))\n"
    "items = list(v.items()) if isinstance(v, dict) else list(enumerate(v))\n"
    "k, x = items[0]\n"
    "print('sample key:', k)\n"
    "print('sample val:', json.dumps(x, ensure_ascii=False)[:400])\n"
    "# find non-CONFIRMED\n"
    "def vd(x):\n"
    "    return x.get('verdict') if isinstance(x, dict) else None\n"
    "for k, x in items:\n"
    "    w = vd(x)\n"
    "    if w and w not in ('CONFIRMED', 'OUT_OF_SCOPE_NON_NUMERIC'):\n"
    "        print(w, '|', k, '|', json.dumps(x, ensure_ascii=False)[:260])\n"
    "EOF\n"
)
CMD3 = (
    "grep -n 'STAGE1_DONE\\|def main\\|while True\\|break\\|drained\\|sys.exit\\|return' /root/mk_v2/_b9_stage1_chain.py | tail -30; echo SEP; "
    "sed -n '/STAGE1_DONE.touch\\|STAGE1_DONE.exists/,+12p' /root/mk_v2/_b9_stage1_chain.py | head -50"
)

c = _remote.connect()
print('##### cmd_run 491-545 #####')
_, o, _ = _remote.run(c, CMD1, timeout=60, echo=False)
print(o)
print('##### verdict schema #####')
_, o, _ = _remote.run(c, CMD2, timeout=60, echo=False)
print(o)
print('##### stage1 loop end #####')
_, o, _ = _remote.run(c, CMD3, timeout=60, echo=False)
c.close()
print(o)
print('ADV_INSPECT5_DONE')
