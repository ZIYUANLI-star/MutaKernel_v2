"""Morning full report: Lane M 12h-post-lever status + closed ledger integrity."""
import _remote as R

py = r"""
import json, glob, os, time, subprocess
from collections import Counter

base = '/root/mk_v2_runs/e3_campaign'

print('=== processes ===')
r = subprocess.run(['pgrep', '-af', 'run_fse_[e]xperiment'],
                   capture_output=True, text=True).stdout.strip()
print('runner:', ('ALIVE ' + r.split()[0]) if r else 'DOWN')
g = subprocess.run(['pgrep', '-af', 'guard_[l]ane_m'],
                   capture_output=True, text=True).stdout.strip()
print('guard:', 'ALIVE' if g else 'DOWN')
gpu = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used',
                      '--format=csv,noheader'], capture_output=True,
                     text=True).stdout.strip()
print('gpu now:', gpu)
print('guard log tail:')
print(open(base + '/guard_lane_m.log').read().strip().split('\n')[-3:])

print('=== observations ===')
rows = []
f = base + '/lane_m_run/observations.jsonl'
for line in open(f):
    if line.strip():
        rows.append(json.loads(line))
print('total obs:', len(rows))
print('newest obs age s:', int(time.time() - os.path.getmtime(f)))

vc = Counter()
walls = []
for r_ in rows:
    vc[r_.get('validation_status')] += 1
    w = r_.get('parent_wall_ms')
    if w:
        walls.append(w / 1000.0)
print('validation_status:', dict(vc.most_common()))
ds = Counter(r_.get('dataset') for r_ in rows)
print('dataset:', dict(ds))
subj = set(r_.get('subject_id') for r_ in rows)
print('distinct subjects:', len(subj))
pairs_failed = set()
pairs_seen = set()
for r_ in rows:
    k = (r_.get('subject_id'), r_.get('strategy_id'))
    pairs_seen.add(k)
    if r_.get('validation_status') == 'fail':
        pairs_failed.add(k)
print('pairs seen:', len(pairs_seen), ' pairs with fail (skipping rest):',
      len(pairs_failed))
walls.sort()
if walls:
    n = len(walls)
    print('wall s: median %.1f p95 %.1f' % (walls[n//2], walls[int(n*.95)]))
# recent 200 cases speed
rec = walls[-200:] if len(walls) >= 200 else walls
if rec:
    rec2 = sorted(rec)
    print('last-200 wall s: median %.1f' % rec2[len(rec2)//2])

print('=== compile amortization ===')
builds = glob.glob(base + '/lane_m_run/torch_extensions/*/*/build.ninja')
print('compiles:', len(builds), ' obs/compile ratio: %.2f'
      % (len(rows) / max(1, len(builds))))

print('=== closed ledgers integrity ===')
for name, p in [
    ('E1 baseline', '/root/mk_v2_runs/e1/baseline_observations.jsonl'),
    ('B9 final', '/root/mk_v2_runs/e3_b9_calib/b9_calib_final_summary.json'),
]:
    print(name, os.path.getsize(p), 'bytes, mtime',
          time.strftime('%m-%d %H:%M', time.localtime(os.path.getmtime(p))))
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_morning_rpt.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _morning_rpt.py",
      timeout=300)
c.close()
print("MORNING_REPORT_DONE")
