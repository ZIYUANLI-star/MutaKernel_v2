"""Peek at calibration row schema + find ALL calibration row files."""
import _remote as R

peek_py = r"""
import glob, json
files = sorted(glob.glob('/root/mk_v2_runs/e3_b9_calib/calibration*.jsonl'))
for f in files:
    n = sum(1 for l in open(f) if l.strip())
    print(f, n)
r = None
for line in open(files[0]):
    if line.strip():
        r = json.loads(line)
        break
print('row keys:', sorted(r.keys()))
print(json.dumps(r, indent=1)[:900])
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_b9_peek.py", "w") as fh:
    fh.write(peek_py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _b9_peek.py", timeout=120)
c.close()
print("PEEK_DONE")
