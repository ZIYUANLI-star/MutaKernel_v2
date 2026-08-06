"""Dump the 9 machine_proven_equivalent rows + manifest proof entries."""
import _remote as R

check_py = r"""
import json
rows = [json.loads(l) for l in
        open('/root/mk_v2_runs/e1/baseline_observations.jsonl')]
proven = [r for r in rows if r.get('status') == 'machine_proven_equivalent']
man = json.load(open('/root/mk_v2_runs/e1/probe_manifest.json'))
plist = man if isinstance(man, list) else man.get('probes', [])
probes = {p.get('probe_id'): p for p in plist if isinstance(p, dict)}
for r in proven:
    pid = r.get('probe_id')
    p = probes.get(pid, {})
    print('=' * 72)
    print(json.dumps(r, ensure_ascii=False)[:700])
    proof = p.get('proof') or r.get('proof')
    print('--- manifest proof:', json.dumps(proof, ensure_ascii=False)[:600])
    print('--- operator:', p.get('operator_name'), '| fault_class:',
          p.get('fault_class'))
    d = p.get('mutation') or {}
    print('--- mutation:', json.dumps(d, ensure_ascii=False)[:400])
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_proof_check2.py", "w") as fh:
    fh.write(check_py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _proof_check2.py",
      timeout=300)
c.close()
print("PROOF_DUMP_DONE")
