"""Find (a) CSE tolerance-conforming bitwise divergence count, (b) compile
share data for 5.7."""
import _remote as R

py = r"""
import glob, json
from collections import Counter

# (a) CSE completed records: outcome field distribution
outcomes = Counter()
bitwise = 0
detail = Counter()
for f in sorted(glob.glob('/root/mk_v2_runs/e1/cse_completed_lane*.json')):
    if f.endswith('.bak_regrade'):
        continue
    d = json.load(open(f))
    items = d if isinstance(d, list) else list(d.values())
    for r in items:
        if not isinstance(r, dict):
            continue
        outcomes[r.get('outcome') or r.get('status')] += 1
        div = r.get('divergence') or {}
        if isinstance(div, dict) and div:
            detail[div.get('kind') or div.get('type')] += 1
print('CSE outcomes:', dict(outcomes))
print('divergence kinds:', dict(detail))

# also the falsify observation ledger if present
for f in sorted(glob.glob('/root/mk_v2_runs/e1/cse_observations*.jsonl')):
    st = Counter()
    tol_conforming = 0
    for line in open(f):
        if not line.strip():
            continue
        r = json.loads(line)
        st[r.get('outcome')] += 1
        if r.get('bitwise_divergent') and not r.get('spec_violation'):
            tol_conforming += 1
    print(f.split('/')[-1], dict(st), 'tol_conforming_bitwise:', tol_conforming)
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_bp_cse_bw.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _bp_cse_bw.py",
      timeout=180)
print("### timing / compile-share artifacts")
R.run(c, "ls /root/mk_v2_runs/e1/ | grep -iE 'timing|cost|budget|offline' | head",
      timeout=60)
c.close()
print("BW_CHECK_DONE")
