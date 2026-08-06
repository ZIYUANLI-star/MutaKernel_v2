"""Afternoon probe: health + sweep progress + amortization onset."""
import _remote as R

py = r"""
import json, os, time, glob, subprocess
from collections import Counter

base = '/root/mk_v2_runs/e3_campaign'
print('=== health ===')
r = subprocess.run(['pgrep', '-af', 'run_fse_[e]xperiment'],
                   capture_output=True, text=True).stdout.strip()
print('runner:', 'ALIVE' if r else 'DOWN')
g = subprocess.run(['pgrep', '-af', 'guard_[l]ane_m'],
                   capture_output=True, text=True).stdout.strip()
print('guard:', 'ALIVE' if g else 'DOWN')
print('guard log tail:', open(base + '/guard_lane_m.log').read().strip()
      .split('\n')[-1])
gpu = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used',
                      '--format=csv,noheader'], capture_output=True,
                     text=True).stdout.strip()
print('gpu now:', gpu)

f = base + '/lane_m_run/observations.jsonl'
rows = [json.loads(l) for l in open(f) if l.strip()]
print('=== ledger ===')
print('total obs:', len(rows), ' newest age s:',
      int(time.time() - os.path.getmtime(f)))
vc = Counter(r_.get('validation_status') for r_ in rows)
print('verdicts:', dict(vc))
ds = Counter(r_.get('dataset') for r_ in rows)
print('dataset:', dict(ds))

pairs = Counter()
for r_ in rows:
    pairs[(r_['subject_id'], r_['strategy_id'])] += 1
multi = {k: v for k, v in pairs.items() if v > 1}
print('pairs seen:', len(pairs), ' pairs with >1 case (2nd sweep started):',
      len(multi))
subj = set(r_['subject_id'] for r_ in rows)
subj_fail = set(r_['subject_id'] for r_ in rows
                if r_.get('validation_status') == 'fail')
print('subjects:', len(subj), ' with >=1 fail:', len(subj_fail))

# speed trend: median wall of consecutive 100-obs windows (last 5 windows)
walls = [r_.get('parent_wall_ms', 0) / 1000.0 for r_ in rows]
for i in range(max(0, len(walls) - 500), len(walls), 100):
    w = sorted(walls[i:i+100])
    if w:
        print('obs[%d:%d] median wall s: %.1f' % (i, i + len(w), w[len(w)//2]))

builds = len(glob.glob(base + '/lane_m_run/torch_extensions/*/*/build.ninja'))
print('compiles:', builds, ' obs:', len(rows),
      ' cache hits so far:', len(rows) - builds)
"""
c = R.connect()
sftp = c.open_sftp()
with sftp.open("/root/mk_v2/_pm_probe.py", "w") as fh:
    fh.write(py)
sftp.close()
R.run(c, "cd /root/mk_v2 && /root/miniconda3/bin/python -u _pm_probe.py",
      timeout=300)
c.close()
print("PM_PROBE_DONE")
