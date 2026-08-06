"""Locate machine-proof rows + headline replay bundle on the remote."""
import _remote as R

c = R.connect()
cmds = [
    # machine-proven equivalence rows in the equiv ledger
    "/root/miniconda3/bin/python -c \"import json;"
    "rows=[json.loads(l) for l in open('/root/mk_v2_runs/e1/equiv_observations.jsonl')];"
    "mp=[r for r in rows if 'PROVEN' in str(r.get('evidence_grade',''))];"
    "print('grades:', sorted(set(r.get('evidence_grade') for r in rows)));"
    "print('machine-proven rows:', len(mp));"
    "[print(r['probe_id'], r.get('proof_rule'), str(r.get('evidence'))[:120]) for r in mp[:12]]\"",
    # proof/static artifacts
    "ls /root/mk_v2_runs/e1/ | grep -i -E 'proof|static' ",
    # replay bundle
    "ls /root/mk_v2_runs/e1/ | grep -i -E 'replay|bundle|headline'",
    "ls /root/mk_v2_runs/e1/analysis/ 2>/dev/null | head -20",
]
for cmd in cmds:
    print("### " + cmd[:80])
    R.run(c, cmd, timeout=180)
c.close()
print("LOCATE_DONE")
