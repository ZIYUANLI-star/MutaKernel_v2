"""Classify failure reasons across all controls_incomplete units."""
import _remote

CMD = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json, glob, os, re\n"
    "from collections import Counter\n"
    "base = '/root/mk_v2_runs/e3_b9_calib/units/'\n"
    "qs = json.load(open('/root/mk_v2_runs/e3_b9_calib/queue_state.json'))\n"
    "ci = sorted(u for u, s in qs['done'].items() if s == 'controls_incomplete')\n"
    "buckets = Counter()\n"
    "examples = {}\n"
    "for u in ci:\n"
    "    obs = glob.glob(base + u + '/*observations*.jsonl')\n"
    "    if not obs:\n"
    "        buckets['NO_OBS_FILE'] += 1\n"
    "        continue\n"
    "    reasons = Counter()\n"
    "    for line in open(obs[0]):\n"
    "        if not line.strip():\n"
    "            continue\n"
    "        r = json.loads(line)\n"
    "        if r.get('status') != 'PASS':\n"
    "            reason = str(r.get('reason', ''))[:80]\n"
    "            reason = re.sub(r'0x[0-9a-f]+', '0xX', reason)\n"
    "            reasons[reason] += 1\n"
    "    if not reasons:\n"
    "        key = 'ALL_PASS(other cause)'\n"
    "    else:\n"
    "        key = reasons.most_common(1)[0][0]\n"
    "    buckets[key] += 1\n"
    "    examples.setdefault(key, u)\n"
    "print('units by dominant failure reason:')\n"
    "for k, v in buckets.most_common():\n"
    "    print(f'  {v:4d}  {k!r}   e.g. {examples.get(k)}')\n"
    "EOF\n"
)

c = _remote.connect()
_, o, _ = _remote.run(c, CMD, timeout=300, echo=False)
c.close()
print(o)
print("DONE3")
