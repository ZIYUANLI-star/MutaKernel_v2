"""Probe C3 frame fields + reconcile_corpora C3 materializer conventions."""
import _remote as R

py = r"""
import json
row = None
for line in open('/root/mk_v2_runs/e2_reconcile/C3_subject_frame.jsonl'):
    row = json.loads(line)
    break
print('frame row keys:', sorted(row.keys()))
for k, v in row.items():
    s = json.dumps(v)
    print(k, ':', s[:200])
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_e3_c3probe.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _e3_c3probe.py",
      timeout=120)
R.run(c, "grep -n 'C3\\|cuda\\|kernel' /root/mk_v2/scripts/reconcile_corpora.py "
         "| head -30", timeout=60)
c.close()
print("C3_PROBE_DONE")
