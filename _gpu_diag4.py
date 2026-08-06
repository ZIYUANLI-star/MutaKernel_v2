"""Compute Lane M completion: planned rows vs done rows, ETA."""
import _remote as R

c = R.connect()
R.run(c, "/root/miniconda3/bin/python - <<'EOF'\n"
         "import json, collections\n"
         "plan=json.load(open('/root/mk_v2_runs/e3_campaign/wave1_lane_m_plan_v2.json'))\n"
         "print('plan top keys:', list(plan.keys()))\n"
         "for k,v in plan.items():\n"
         "    if isinstance(v,list): print(' list', k, len(v))\n"
         "tests=plan.get('tests') or plan.get('rows') or plan.get('entries')\n"
         "if tests: print('sample test:', json.dumps(tests[0])[:300])\n"
         "done=collections.Counter(); done_keys=set()\n"
         "strat=collections.Counter()\n"
         "for l in open('/root/mk_v2_runs/e3_campaign/lane_m_run/observations.jsonl'):\n"
         "    if not l.strip(): continue\n"
         "    r=json.loads(l)\n"
         "    done_keys.add((r['subject_id'], r['strategy_name'], r.get('test_id'), r.get('replicate')))\n"
         "    strat[r['strategy_name']]+=1\n"
         "print('ledger rows (unique keys):', len(done_keys))\n"
         "print('per strategy:', dict(strat))\n"
         "if tests:\n"
         "    total=len(tests)\n"
         "    planned=set()\n"
         "    for t in tests:\n"
         "        planned.add((t.get('subject_id'), t.get('strategy_name'), t.get('test_id'), t.get('replicate')))\n"
         "    print('planned rows:', total, 'unique planned keys:', len(planned))\n"
         "    remaining=planned-done_keys\n"
         "    print('remaining:', len(remaining))\n"
         "    rem_subj=collections.Counter(k[0].split('__')[0] for k in remaining if k[0])\n"
         "    print('remaining by corpus:', dict(rem_subj))\n"
         "EOF", timeout=600)
c.close()
print("DIAG4_DONE")
