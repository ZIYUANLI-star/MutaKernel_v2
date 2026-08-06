import _remote

c = _remote.connect()
cmd = (
    "python3 - <<'EOF'\n"
    "import json, collections\n"
    "recs = [json.loads(l) for l in open('/root/mk_v2_runs/e1/baseline_observations.jsonl') if l.strip()]\n"
    "print('total', len(recs))\n"
    "print(collections.Counter(r.get('status') for r in recs))\n"
    "for r in recs:\n"
    "    if r.get('status') in ('unknown', 'stillborn'):\n"
    "        print('---', r.get('probe_id'), r.get('status'))\n"
    "        print('   err:', (r.get('error') or r.get('error_message') or '')[:300])\n"
    "excl = collections.Counter(r.get('problem_name') for r in recs if r.get('status') == 'excluded_control_failed')\n"
    "print('excluded by problem:', dict(excl))\n"
    "EOF"
)
_, out, _ = _remote.run(c, cmd, timeout=120, echo=False)
c.close()
print(out)
print("ANOMALY_DONE")
