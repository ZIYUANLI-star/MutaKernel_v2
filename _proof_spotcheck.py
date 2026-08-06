"""Spot-check the 9 machine-proven equivalences (acting reviewer).

Pulls each PROVEN row from baseline_observations.jsonl with its rule id and
evidence, plus the probe's mutation descriptor from probe_manifest.json, and
prints them side by side so the reviewer (agent, delegated) can verify that
the static rule's premise actually holds for the mutation.
"""
import _remote as R

check_py = r"""
import json
rows = [json.loads(l) for l in
        open('/root/mk_v2_runs/e1/baseline_observations.jsonl')]
proven = [r for r in rows if 'PROVEN' in str(r.get('status', '')) or
          'PROVEN' in str(r.get('evidence_grade', ''))]
print('PROVEN rows:', len(proven))
man = json.load(open('/root/mk_v2_runs/e1/probe_manifest.json'))
probes = {p['probe_id']: p for p in man.get('probes', [])} \
    if isinstance(man, dict) else {}
for r in proven:
    pid = r.get('probe_id')
    p = probes.get(pid, {})
    print('=' * 70)
    print('probe:', pid)
    print('status/grade:', r.get('status'), r.get('evidence_grade'))
    print('proof fields:', json.dumps({k: v for k, v in r.items()
          if 'proof' in k.lower() or 'rule' in k.lower() or 'static' in k.lower()},
          ensure_ascii=False)[:400])
    print('evidence:', json.dumps(r.get('evidence'), ensure_ascii=False)[:400])
    print('mutation:', json.dumps({k: p.get(k) for k in
          ('operator_name', 'fault_class', 'mutation', 'site', 'diff')
          if k in p}, ensure_ascii=False)[:500])
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_proof_check.py", "w") as fh:
    fh.write(check_py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _proof_check.py",
      timeout=300)
c.close()
print("PROOF_LIST_DONE")
