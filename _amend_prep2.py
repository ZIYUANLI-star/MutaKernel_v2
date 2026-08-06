import _remote

c = _remote.connect()
CMD = (
    "/root/miniconda3/bin/python - <<'EOF'\n"
    "import json, glob\n"
    "rep = json.load(open('/root/mk_v2_runs/e1/witness_confirmation/wc1_report.json'))\n"
    "for v in rep['verdicts']:\n"
    "    if v.get('probe_id') in ('L2_P68__relop_replace__3', 'L2_P98__mask_boundary__3',\n"
    "                             'L1_P94__const_perturb__7', 'L1_P95__relop_replace__5'):\n"
    "        print(json.dumps(v, ensure_ascii=False)[:800])\n"
    "        print()\n"
    "# locate ledger rows\n"
    "targets = {'L1_P37__sync_remove__1', 'L1_P94__const_perturb__7', 'L1_P96__relop_replace__8'}\n"
    "for f in sorted(glob.glob('/root/mk_v2_runs/e1/cse_observations_lane*.jsonl')):\n"
    "    hits = []\n"
    "    for line in open(f):\n"
    "        r = json.loads(line)\n"
    "        if r.get('probe_id') in targets:\n"
    "            hits.append((r['probe_id'], r.get('outcome')))\n"
    "    if hits:\n"
    "        print(f.split('/')[-1], hits)\n"
    "# equiv ledger structure\n"
    "n = 0\n"
    "from collections import Counter\n"
    "cnt = Counter()\n"
    "p37 = []\n"
    "for line in open('/root/mk_v2_runs/e1/equiv_observations.jsonl'):\n"
    "    r = json.loads(line)\n"
    "    n += 1\n"
    "    cnt[r.get('evidence_grade') or r.get('validation_status')] += 1\n"
    "    if r.get('probe_id', '').startswith(('L1_P37__', 'L1_P49__sync', 'L2_P63__sync',\n"
    "                                          'L2_P68__relop_replace__3'[:0])):\n"
    "        pass\n"
    "print('equiv ledger rows:', n, dict(cnt))\n"
    "EOF\n"
)
_, o, e = _remote.run(c, CMD, timeout=90, echo=False)
print(o)
if e.strip():
    print('STDERR:', e[:500])
c.close()
print('DONE')
