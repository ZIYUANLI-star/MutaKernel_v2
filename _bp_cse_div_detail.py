"""Show the SLE record carrying a divergence annotation + falsified records."""
import _remote as R

py = r"""
import glob, json
for f in sorted(glob.glob('/root/mk_v2_runs/e1/cse_observations*.jsonl')):
    for line in open(f):
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get('outcome') == 'STILL_LIKELY_EQUIVALENT' and d.get('divergence'):
            print(f.split('/')[-1], d['probe_id'])
            print(json.dumps(d['divergence'], indent=1)[:800])
            print('validation_status:', d.get('validation_status'))
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_bp_cse_dd.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _bp_cse_dd.py",
      timeout=180)
c.close()
print("DIV_DETAIL_DONE")
