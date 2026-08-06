"""Diagnose whether Lane M runner is compiling (CPU-busy) or stalled."""
import _remote as R

py = r"""
import subprocess, os, glob, time, json
from collections import Counter

# process tree CPU
out = subprocess.run(['ps', '-eo', 'pid,ppid,pcpu,pmem,etimes,stat,cmd',
                      '--sort=-pcpu'], capture_output=True, text=True).stdout
lines = [l for l in out.splitlines()
         if any(s in l for s in ('run_fse', 'ninja', 'nvcc', 'cicc', 'g++',
                                 'cc1plus', 'python'))][:15]
print('\n'.join(lines))

# runner children
try:
    ch = subprocess.run(['ps', '--ppid', '531990', '-o', 'pid,pcpu,etimes,cmd'],
                        capture_output=True, text=True).stdout
    print('children of 531990:\n', ch)
except Exception as e:
    print('ps children err', e)

# artifact mtime timeline: newest 15 files under lane_m_run
base = '/root/mk_v2_runs/e3_campaign'
allf = []
for root, dirs, files in os.walk(base + '/lane_m_run'):
    for fn in files:
        p = os.path.join(root, fn)
        try:
            allf.append((os.path.getmtime(p), p))
        except OSError:
            pass
allf.sort()
now = time.time()
print('total artifact files:', len(allf))
for m, p in allf[-12:]:
    print(f'{int(now-m):>6}s ago  {p.split("lane_m_run/")[-1][:110]}')

# verdict distribution from worker_result
rows = []
for f in glob.glob(base + '/**/observations.jsonl', recursive=True):
    for line in open(f):
        if line.strip():
            rows.append(json.loads(line))
vc = Counter()
for r in rows:
    wr = r.get('worker_result') or {}
    vc[(r.get('validation_status'), (wr.get('status') or wr.get('verdict')))] += 1
print('verdicts (validation_status, worker.status):', dict(vc.most_common()))
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_lm_stall.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _lm_stall.py",
      timeout=300)
c.close()
print("STALL_DIAG_DONE")
